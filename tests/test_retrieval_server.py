from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.source_policy import SourceCategory
from services.guidance.answer_evaluation import AnswerEvaluation
from services.retrieval.server import RetrievalServerError, RuntimeState, _cgc_failure_message, _github_repository_from_remote_url, _local_ui_url, _oauth_redirect_uri, _safe_run_id, _sync_cgcignore


VALID_ENV = "\n".join(
    [
        "RETRIEVAL_LLM_MODEL=test",
        "RETRIEVAL_LLM_API_STYLE=openai_chat_completions",
        "RETRIEVAL_LLM_ENDPOINT_URL=http://example.test/llm",
        "RETRIEVAL_LLM_API_KEY=key",
        "RETRIEVAL_EMBEDDING_MODEL=embed",
        "RETRIEVAL_EMBEDDING_API_STYLE=openai_embeddings",
        "RETRIEVAL_EMBEDDING_ENDPOINT_URL=http://example.test/embed",
        "RETRIEVAL_EMBEDDING_API_KEY=key",
        "RETRIEVAL_QDRANT_URL=http://localhost:6333",
        "RETRIEVAL_QDRANT_COLLECTION=test",
    ]
)


class RetrievalServerStateTests(unittest.TestCase):
    def test_oauth_callback_return_url_points_to_local_ui(self) -> None:
        self.assertEqual(_local_ui_url("127.0.0.1:8790"), "http://127.0.0.1:5173/#connections")

    def test_oauth_callback_return_url_uses_local_ui_when_redirect_is_public(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text("OAUTH_REDIRECT_BASE_URL=https://example.ngrok-free.dev/\n", encoding="utf-8")

            self.assertEqual(_local_ui_url("example.ngrok-free.dev", root), "http://127.0.0.1:5173/#connections")

    def test_oauth_callback_return_url_can_be_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text("OAUTH_RETURN_BASE_URL=http://localhost:5173/\n", encoding="utf-8")

            self.assertEqual(_local_ui_url("example.ngrok-free.dev", root), "http://localhost:5173/#connections")

    def test_oauth_redirect_uri_uses_configured_public_base_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text("OAUTH_REDIRECT_BASE_URL=https://example.ngrok-free.dev/\n", encoding="utf-8")

            self.assertEqual(
                _oauth_redirect_uri("127.0.0.1:8790", root),
                "https://example.ngrok-free.dev/connections/provider-auth/callback",
            )

    def test_health_reports_default_workspace_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tool_root = root / "tool"
            workspace = root / "workspace"
            tool_root.mkdir()
            workspace.mkdir()
            state = RuntimeState(workspace, tool_root=tool_root)

            health = state.public_health()

            self.assertEqual(health["status"], "ok")
            self.assertEqual(health["workspace_root"], str(workspace.resolve()))
            self.assertFalse(health["config_exists"])
            self.assertFalse(health["env_exists"])

    def test_health_checks_tool_env_not_selected_workspace_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            tool_root = root / "tool"
            workspace.mkdir()
            tool_root.mkdir()
            (tool_root / ".env").write_text(VALID_ENV, encoding="utf-8")
            state = RuntimeState(workspace, tool_root=tool_root)

            with patch("services.retrieval.server._qdrant_reachable", return_value=True):
                health = state.public_health()

            self.assertEqual(health["workspace_root"], str(workspace.resolve()))
            self.assertEqual(health["tool_root"], str(tool_root.resolve()))
            self.assertTrue(health["env_exists"])
            self.assertTrue(health["llm_configured"])
            self.assertTrue(health["embedding_configured"])
            self.assertTrue(health["qdrant_configured"])
            self.assertTrue(health["qdrant_reachable"])

    def test_ensure_qdrant_runtime_reports_docker_engine_problem(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            tool_root = root / "tool"
            workspace.mkdir()
            tool_root.mkdir()
            (tool_root / ".env").write_text(VALID_ENV, encoding="utf-8")
            (tool_root / "docker-compose.qdrant.yml").write_text("services: {}\n", encoding="utf-8")
            state = RuntimeState(workspace, tool_root=tool_root)
            completed = type(
                "Completed",
                (),
                {
                    "returncode": 1,
                    "stderr": "open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.",
                    "stdout": "",
                },
            )()

            with patch("services.retrieval.server._qdrant_reachable", return_value=False), patch(
                "services.retrieval.server.subprocess.run",
                return_value=completed,
            ):
                with self.assertRaisesRegex(Exception, "Docker Desktop is not running"):
                    state.ensure_qdrant_runtime()

    def test_update_config_persists_non_secret_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state = RuntimeState(root)

            config = state.update_config(
                {
                    "enabled_source_categories": ["source_code", "issue_tracker"],
                    "enabled_sources": ["source_code", "github_issues"],
                    "connections": {
                        "github_repository": "owner/repo",
                        "github_fetch_issues": True,
                        "mcp_sources": [
                            {
                                "name": "github-issues",
                                "source_category": "issue_tracker",
                                "source_key": "github_issues",
                                "command": "example-mcp",
                                "args": ["--stdio"],
                                "env": {"GITHUB_TOKEN": "secret"},
                                "query_tool_name": "search_issues",
                                "query_argument_name": "q",
                                "limit_argument_name": "first",
                                "result_limit": 3,
                                "timeout_seconds": 12,
                                "static_tool_arguments": {"repo": "owner/repo"},
                                "id_fields": ["html_url", "number"],
                                "title_fields": ["title"],
                                "content_fields": ["body"],
                            }
                        ]
                    },
                    "intent": {"shadow_mode": True, "assistance_mode": "active"},
                }
            )

            self.assertTrue((root / ".guided-intelligence" / "config.json").exists())
            self.assertEqual(config["enabled_sources"], ["source_code", "github_issues"])
            self.assertEqual(config["enabled_source_categories"], ["source_code", "issue_tracker"])
            self.assertNotIn("github_repository", config["connections"])
            self.assertNotIn("github_fetch_issues", config["connections"])
            self.assertEqual(config["connections"]["mcp_sources"][0]["name"], "github-issues")
            self.assertEqual(config["connections"]["mcp_sources"][0]["source_key"], "github_issues")
            self.assertEqual(config["connections"]["mcp_sources"][0]["env"]["GITHUB_TOKEN"], "secret")
            self.assertEqual(config["connections"]["mcp_sources"][0]["static_tool_arguments"]["repo"], "owner/repo")
            self.assertEqual(config["connections"]["mcp_sources"][0]["content_fields"], ["body"])
            self.assertTrue(config["intent"]["shadow_mode"])
            self.assertNotIn("router_mode", config["intent"])
            self.assertEqual(config["intent"]["assistance_mode"], "active")

    def test_old_enabled_source_categories_migrate_to_source_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_dir = root / ".guided-intelligence"
            config_dir.mkdir()
            (config_dir / "config.json").write_text(
                json.dumps(
                    {
                        "enabled_source_categories": ["source_code", "documentation", "issue_tracker"],
                        "connections": {
                            "remote_mcp_sources": [
                                {
                                    "enabled": True,
                                    "name": "shortcut-stories",
                                    "provider": "shortcut",
                                    "source_category": "issue_tracker",
                                    "endpoint_url": "http://remote.test/mcp",
                                    "query_tool_name": "stories-search",
                                },
                                {
                                    "enabled": False,
                                    "name": "notion-pages",
                                    "provider": "notion",
                                    "source_category": "documentation",
                                    "endpoint_url": "http://remote.test/mcp",
                                    "query_tool_name": "notion-search",
                                },
                            ],
                            "mcp_sources": [],
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = RuntimeState(root).get_config()

            self.assertEqual(config["enabled_sources"], ["source_code", "repo_docs", "shortcut"])
            self.assertEqual(config["enabled_source_categories"], ["source_code", "documentation", "issue_tracker"])

    def test_remote_mcp_tool_listing_uses_remote_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = RuntimeState(Path(temp_dir))
            state.update_provider_auth({"provider": "notion", "auth_type": "bearer", "bearer_token": "token"})

            with patch("services.retrieval.server.RemoteMCPConnectedSourceAdapter") as adapter_class:
                adapter_class.return_value.list_tools.return_value = ({"name": "search_pages"},)
                result = state.list_remote_mcp_tools(
                    {
                        "enabled": True,
                        "name": "notion-pages",
                        "provider": "notion",
                        "source_category": "documentation",
                        "endpoint_url": "http://remote.test/mcp",
                        "query_tool_name": "search_pages",
                    }
                )

            self.assertTrue(result["ok"])
            self.assertEqual(result["tool_count"], 1)
            self.assertEqual(result["tools"][0]["name"], "search_pages")
            adapter_config = adapter_class.call_args.args[0]
            self.assertEqual(adapter_config.bearer_token, "token")

    def test_provider_auth_is_tool_scoped_and_public_response_hides_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tool_root = root / "tool"
            workspace_a = root / "workspace-a"
            workspace_b = root / "workspace-b"
            tool_root.mkdir()
            workspace_a.mkdir()
            workspace_b.mkdir()
            state_a = RuntimeState(workspace_a, tool_root=tool_root)

            public_auth = state_a.update_provider_auth(
                {"provider": "notion", "auth_type": "bearer", "bearer_token": "secret-token"}
            )
            state_b = RuntimeState(workspace_b, tool_root=tool_root)

            self.assertTrue(public_auth["notion"]["connected"])
            self.assertTrue(public_auth["notion"]["bearer_token_configured"])
            self.assertNotIn("secret-token", json.dumps(public_auth))
            self.assertTrue(state_b.public_provider_auth()["notion"]["connected"])
            self.assertTrue((tool_root / ".guided-intelligence" / "provider-auth.json").exists())

    def test_provider_oauth_start_returns_browser_authorize_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            tool_root = root / "tool"
            workspace.mkdir()
            tool_root.mkdir()
            state = RuntimeState(workspace, tool_root=tool_root)

            with patch.dict("os.environ", {}, clear=True), patch(
                "services.retrieval.server._discover_oauth_metadata",
                return_value={
                    "authorization_endpoint": "https://auth.example/authorize",
                    "token_endpoint": "https://auth.example/token",
                    "resource": "https://remote.example/mcp",
                },
            ), patch(
                "services.retrieval.server._register_oauth_client",
                return_value={"client_id": "client-1"},
            ):
                result = state.start_provider_oauth(
                    {"provider": "github", "endpoint_url": "https://remote.example/mcp", "oauth_scope": "repo"},
                    request_host="127.0.0.1:8790",
                )

            self.assertTrue(result["ok"])
            self.assertIn("https://auth.example/authorize?", result["authorize_url"])
            self.assertIn("client_id=client-1", result["authorize_url"])
            self.assertIn("code_challenge=", result["authorize_url"])
            self.assertIn("scope=repo", result["authorize_url"])

    def test_provider_oauth_callback_stores_access_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            tool_root = root / "tool"
            workspace.mkdir()
            tool_root.mkdir()
            state = RuntimeState(workspace, tool_root=tool_root)
            with patch.dict("os.environ", {}, clear=True), patch(
                "services.retrieval.server._discover_oauth_metadata",
                return_value={
                    "authorization_endpoint": "https://auth.example/authorize",
                    "token_endpoint": "https://auth.example/token",
                    "resource": "https://remote.example/mcp",
                },
            ), patch(
                "services.retrieval.server._register_oauth_client",
                return_value={"client_id": "client-1"},
            ):
                result = state.start_provider_oauth(
                    {"provider": "github", "endpoint_url": "https://remote.example/mcp"},
                    request_host="127.0.0.1:8790",
                )
            state_value = result["authorize_url"].split("state=", 1)[1].split("&", 1)[0]

            with patch("services.retrieval.server._post_form_json", return_value={"access_token": "oauth-token"}):
                provider = state.finish_provider_oauth({"state": [state_value], "code": ["code-1"]})

            self.assertEqual(provider, "github")
            public_auth = state.public_provider_auth()
            self.assertTrue(public_auth["github"]["connected"])
            self.assertTrue(public_auth["github"]["oauth_access_token_configured"])

    def test_github_oauth_uses_tool_configured_client_when_dynamic_registration_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            tool_root = root / "tool"
            workspace.mkdir()
            tool_root.mkdir()
            (tool_root / ".env").write_text(
                VALID_ENV
                + "\nGITHUB_OAUTH_CLIENT_ID=github-client\nGITHUB_OAUTH_CLIENT_SECRET=github-secret\nGITHUB_OAUTH_SCOPE=repo\n",
                encoding="utf-8",
            )
            state = RuntimeState(workspace, tool_root=tool_root)

            with patch(
                "services.retrieval.server._discover_oauth_metadata",
                return_value={
                    "authorization_endpoint": "https://unused.example/authorize",
                    "token_endpoint": "https://unused.example/token",
                    "resource": "https://api.githubcopilot.com/mcp/",
                },
            ), patch("services.retrieval.server._register_oauth_client") as register:
                result = state.start_provider_oauth(
                    {
                        "provider": "github",
                        "endpoint_url": "https://api.githubcopilot.com/mcp/",
                        "scope": "owner/repo",
                    },
                    request_host="127.0.0.1:8790",
                )

            self.assertIn("https://github.com/login/oauth/authorize?", result["authorize_url"])
            self.assertIn("client_id=github-client", result["authorize_url"])
            self.assertIn("scope=repo", result["authorize_url"])
            self.assertNotIn("owner%2Frepo", result["authorize_url"])
            register.assert_not_called()

            state_value = result["authorize_url"].split("state=", 1)[1].split("&", 1)[0]
            with patch("services.retrieval.server._post_form_json", return_value={"access_token": "oauth-token"}) as post_form:
                state.finish_provider_oauth({"state": [state_value], "code": ["code-1"]})
            token_payload = post_form.call_args.args[1]
            self.assertEqual(token_payload["client_id"], "github-client")
            self.assertEqual(token_payload["client_secret"], "github-secret")

    def test_github_oauth_reports_missing_tool_level_client(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            tool_root = root / "tool"
            workspace.mkdir()
            tool_root.mkdir()
            state = RuntimeState(workspace, tool_root=tool_root)

            with patch.dict("os.environ", {}, clear=True), patch(
                "services.retrieval.server._discover_oauth_metadata",
                return_value={
                    "authorization_endpoint": "https://unused.example/authorize",
                    "token_endpoint": "https://unused.example/token",
                    "resource": "https://api.githubcopilot.com/mcp/",
                },
            ):
                with self.assertRaisesRegex(RetrievalServerError, "GITHUB_OAUTH_CLIENT_ID"):
                    state.start_provider_oauth(
                        {"provider": "github", "endpoint_url": "https://api.githubcopilot.com/mcp/"},
                        request_host="127.0.0.1:8790",
                    )

    def test_notion_oauth_uses_hosted_mcp_discovery_and_dynamic_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            tool_root = root / "tool"
            workspace.mkdir()
            tool_root.mkdir()
            (tool_root / ".env").write_text(VALID_ENV, encoding="utf-8")
            state = RuntimeState(workspace, tool_root=tool_root)

            with patch(
                "services.retrieval.server._discover_oauth_metadata",
                return_value={
                    "authorization_endpoint": "https://mcp.notion.com/authorize",
                    "token_endpoint": "https://mcp.notion.com/token",
                    "registration_endpoint": "https://mcp.notion.com/register",
                    "resource": "https://mcp.notion.com/mcp",
                },
            ), patch(
                "services.retrieval.server._register_oauth_client",
                return_value={"client_id": "dynamic-notion-client", "pkce": True, "token_auth_method": "form"},
            ) as register:
                result = state.start_provider_oauth(
                    {"provider": "notion", "endpoint_url": "https://mcp.notion.com/mcp"},
                    request_host="127.0.0.1:8790",
                )

            self.assertIn("https://mcp.notion.com/authorize?", result["authorize_url"])
            self.assertIn("client_id=dynamic-notion-client", result["authorize_url"])
            self.assertIn("code_challenge", result["authorize_url"])
            self.assertIn("resource=https%3A%2F%2Fmcp.notion.com%2Fmcp", result["authorize_url"])
            self.assertNotIn("owner=user", result["authorize_url"])
            register.assert_called_once()
            self.assertEqual(
                register.call_args.kwargs["redirect_uri"],
                "http://127.0.0.1:8790/connections/provider-auth/callback",
            )

            state_value = result["authorize_url"].split("state=", 1)[1].split("&", 1)[0]
            with patch("services.retrieval.server._post_form_json", return_value={"access_token": "oauth-token"}) as post_form:
                state.finish_provider_oauth({"state": [state_value], "code": ["code-1"]})
            self.assertEqual(post_form.call_args.args[0], "https://mcp.notion.com/token")
            self.assertEqual(post_form.call_args.args[1]["client_id"], "dynamic-notion-client")
            self.assertEqual(post_form.call_args.args[1]["code"], "code-1")

    def test_notion_oauth_reports_missing_hosted_mcp_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            tool_root = root / "tool"
            workspace.mkdir()
            tool_root.mkdir()
            state = RuntimeState(workspace, tool_root=tool_root)

            with patch.dict("os.environ", {}, clear=True), patch(
                "services.retrieval.server._discover_oauth_metadata",
                return_value={
                    "authorization_endpoint": "https://unused.example/authorize",
                    "token_endpoint": "https://unused.example/token",
                    "resource": "https://mcp.notion.com/mcp",
                },
            ):
                with self.assertRaisesRegex(RetrievalServerError, "dynamic client registration"):
                    state.start_provider_oauth(
                        {"provider": "notion", "endpoint_url": "https://mcp.notion.com/mcp"},
                        request_host="127.0.0.1:8790",
                    )

    def test_shortcut_connect_uses_tool_level_api_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            tool_root = root / "tool"
            workspace.mkdir()
            tool_root.mkdir()
            (tool_root / ".env").write_text(VALID_ENV + "\nSHORTCUT_API_TOKEN=shortcut-token\n", encoding="utf-8")
            state = RuntimeState(workspace, tool_root=tool_root)

            result = state.start_provider_oauth(
                {"provider": "shortcut", "endpoint_url": "https://mcp.shortcut.com/mcp"},
                request_host="127.0.0.1:8790",
            )

            self.assertTrue(result["ok"])
            public_auth = state.public_provider_auth()
            self.assertTrue(public_auth["shortcut"]["connected"])
            self.assertTrue(public_auth["shortcut"]["bearer_token_configured"])

    def test_shortcut_connect_reports_missing_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            tool_root = root / "tool"
            workspace.mkdir()
            tool_root.mkdir()
            state = RuntimeState(workspace, tool_root=tool_root)

            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(RetrievalServerError, "SHORTCUT_API_TOKEN"):
                    state.start_provider_oauth(
                        {"provider": "shortcut", "endpoint_url": "https://mcp.shortcut.com/mcp"},
                        request_host="127.0.0.1:8790",
                    )

    def test_workspace_retrieval_config_omits_disabled_mcp_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tool_root = root / "tool"
            workspace = root / "workspace"
            tool_root.mkdir()
            workspace.mkdir()
            (tool_root / ".env").write_text(VALID_ENV, encoding="utf-8")
            state = RuntimeState(workspace, tool_root=tool_root)
            state.update_config(
                {
                    "connections": {
                        "mcp_sources": [
                            {
                                "enabled": False,
                                "name": "github-disabled",
                                "source_category": "issue_tracker",
                                "command": "example-mcp",
                                "query_tool_name": "search_issues",
                            },
                            {
                                "enabled": True,
                                "name": "github-enabled",
                                "source_category": "pull_request",
                                "command": "example-mcp",
                                "query_tool_name": "search_pull_requests",
                            },
                        ]
                    }
                }
            )

            config = state._workspace_retrieval_config(run_dir=workspace / ".guided-intelligence" / "runs" / "test")

            self.assertEqual([source.name for source in config.mcp_connected_sources], ["github-enabled"])
            self.assertEqual(config.mcp_connected_sources[0].source_category.value, "pull_request")

    def test_default_config_includes_hosted_remote_mcp_provider_cards(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = RuntimeState(Path(temp_dir))

            self.assertNotIn("response_pipeline", state.get_config()["assistance"])
            self.assertEqual(state.get_config()["assistance"]["mode"], "teach")
            self.assertFalse(state.get_config()["intent"]["shadow_mode"])
            self.assertNotIn("router_mode", state.get_config()["intent"])
            self.assertEqual(state.get_config()["intent"]["assistance_mode"], "off")
            sources = state.get_config()["connections"]["remote_mcp_sources"]
            providers = {source["provider"] for source in sources}
            endpoints = {source["provider"]: source["endpoint_url"] for source in sources}
            by_name = {source["name"]: source for source in sources}

            self.assertIn("github", providers)
            self.assertIn("notion", providers)
            self.assertIn("atlassian", providers)
            self.assertIn("shortcut", providers)
            self.assertIn("linear", providers)
            self.assertIn("slack", providers)
            self.assertIn("google_drive", providers)
            self.assertEqual(endpoints["github"], "https://api.githubcopilot.com/mcp/")
            self.assertEqual(endpoints["notion"], "https://mcp.notion.com/mcp")
            self.assertEqual(endpoints["shortcut"], "https://mcp.shortcut.com/mcp")
            self.assertEqual(endpoints["linear"], "https://mcp.linear.app/sse")
            self.assertEqual(endpoints["google_drive"], "https://drivemcp.googleapis.com/mcp/v1")
            self.assertEqual(by_name["notion-pages"]["query_tool_name"], "notion-search")
            self.assertEqual(by_name["notion-pages"]["fetch_tool_name"], "notion-fetch")
            self.assertTrue(by_name["notion-pages"]["enrich_results"])
            self.assertEqual(by_name["notion-pages"]["enrich_limit"], 3)
            self.assertEqual(
                by_name["notion-pages"]["features"],
                {"pages": True, "databases": True, "data_sources": True, "comments": False},
            )

    def test_remote_mcp_defaults_repair_blank_github_query_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = RuntimeState(Path(temp_dir))

            state.update_config(
                {
                    "connections": {
                        "remote_mcp_sources": [
                            {
                                "enabled": True,
                                "name": "github-issues",
                                "provider": "github",
                                "source_category": "issue_tracker",
                                "endpoint_url": "https://api.githubcopilot.com/mcp/",
                                "query_tool_name": "",
                            },
                            {
                                "enabled": True,
                                "name": "github-prs",
                                "provider": "github",
                                "source_category": "pull_request",
                                "endpoint_url": "https://api.githubcopilot.com/mcp/",
                                "query_tool_name": "",
                            },
                        ]
                    }
                }
            )

            sources = {
                source["name"]: source
                for source in state.get_config()["connections"]["remote_mcp_sources"]
            }

            self.assertEqual(sources["github-issues"]["query_tool_name"], "search_issues")
            self.assertEqual(sources["github-prs"]["query_tool_name"], "search_pull_requests")

    def test_workspace_retrieval_config_loads_enabled_remote_mcp_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tool_root = root / "tool"
            workspace = root / "workspace"
            tool_root.mkdir()
            workspace.mkdir()
            (tool_root / ".env").write_text(VALID_ENV, encoding="utf-8")
            state = RuntimeState(workspace, tool_root=tool_root)
            state.update_provider_auth({"provider": "notion", "auth_type": "bearer", "bearer_token": "token"})
            state.update_config(
                {
                    "connected_context": {
                        "disclaimer_required_terms": ["avoid", "current"],
                        "stale_block_terms": ["retired", "obsolete"],
                    },
                    "connections": {
                        "remote_mcp_sources": [
                            {
                                "enabled": True,
                                "name": "notion-pages",
                                "provider": "notion",
                                "source_category": "documentation",
                                "endpoint_url": "http://remote.test/mcp",
                                "auth_type": "bearer",
                                "bearer_token": "workspace-token-should-not-persist",
                                "scope": "workspace-a",
                                "query_tool_name": "search_pages",
                                "min_score": 0.42,
                                "score_fields": ["score", "relevance"],
                            }
                        ],
                        "mcp_sources": [],
                    },
                }
            )

            config = state._workspace_retrieval_config(run_dir=workspace / ".guided-intelligence" / "runs" / "test")

            self.assertEqual([source.name for source in config.remote_mcp_connected_sources], ["notion-pages"])
            self.assertEqual(config.remote_mcp_connected_sources[0].provider, "notion")
            self.assertEqual(config.remote_mcp_connected_sources[0].bearer_token, "token")
            self.assertEqual(config.remote_mcp_connected_sources[0].min_score, 0.42)
            self.assertEqual(config.remote_mcp_connected_sources[0].score_fields, ("score", "relevance"))
            self.assertEqual(config.connected_context_disclaimer_required_terms, ("avoid", "current"))
            self.assertEqual(config.connected_context_stale_block_terms, ("retired", "obsolete"))
            saved_source = state.get_config()["connections"]["remote_mcp_sources"][2]
            self.assertEqual(saved_source["name"], "notion-pages")
            self.assertEqual(saved_source["bearer_token"], "")

    def test_workspace_history_is_tool_scoped_and_ordered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tool_root = root / "tool"
            workspace_a = root / "project-a"
            workspace_b = root / "project-b"
            tool_root.mkdir()
            workspace_a.mkdir()
            workspace_b.mkdir()
            state = RuntimeState(workspace_a, tool_root=tool_root)

            state.remember_workspace(workspace_a)
            state.remember_workspace(workspace_b)
            workspaces = state.list_workspaces()

            self.assertEqual(workspaces[0]["workspace_root"], str(workspace_b.resolve()))
            self.assertEqual(workspaces[1]["workspace_root"], str(workspace_a.resolve()))
            self.assertTrue((tool_root / ".guided-intelligence" / "workspaces.json").exists())
            self.assertFalse((workspace_a / ".guided-intelligence" / "workspaces.json").exists())

    def test_run_listing_reads_existing_run_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state = RuntimeState(root)
            run_dir = root / ".guided-intelligence" / "runs" / "run-1"
            run_dir.mkdir(parents=True)
            (run_dir / "orchestration-result.json").write_text(
                """
{
  "retrieval_result": {
    "coverage_status": "partial",
    "sufficient": false,
    "evidence": [{"source_id": "repo-pre:src/a.ts:L1-L4"}],
    "retrieval_summary": {
      "stop_reason": "late_synthesis_complete",
      "retrieval_plan": {"raw_prompt": "Explain parser behavior."}
    }
  },
  "response_payload": {"content": "Parser behavior explanation."}
}
""".strip(),
                encoding="utf-8",
            )

            runs = state.list_runs()

            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["run_id"], "run-1")
            self.assertEqual(runs[0]["coverage_status"], "partial")
            self.assertEqual(runs[0]["selected_count"], 1)

    def test_comprehension_answer_evaluation_writes_followup_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tool_root = root / "tool"
            workspace = root / "workspace"
            tool_root.mkdir()
            workspace.mkdir()
            (tool_root / ".env").write_text(VALID_ENV, encoding="utf-8")
            state = RuntimeState(workspace, tool_root=tool_root)
            run_dir = workspace / ".guided-intelligence" / "runs" / "run-1"
            run_dir.mkdir(parents=True)
            plan = {
                "task_goal": "Understand validation.",
                "answer_scope": "Explain validation.",
                "assistance_mode": "teach",
                "relevant_artifacts": [
                    {
                        "id": "a1",
                        "path": "src/compiler/checker.ts",
                        "line_range": "L10-L12",
                        "role": "validation_checking",
                        "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                        "claim_supported": "Checker validates semantics.",
                    }
                ],
                "concepts": [
                    {
                        "id": "validation_checking",
                        "name": "validation checking",
                        "role": "core",
                        "description": "Checker validates semantics.",
                        "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                        "status": "grounded",
                        "required_for_answer": True,
                        "suggested_depth": "full",
                    }
                ],
                "concept_dependencies": [],
                "explanation_sequence": [],
                "depth_policy": {
                    "mode": "assumption_statement",
                    "assumption_statement": "Assume basic code navigation.",
                    "gate_required": False,
                    "rationale": "",
                },
                "understanding_check": {
                    "id": "q1",
                    "type": "why",
                    "question": "Why does validation matter?",
                    "expected_points": ["It validates semantics."],
                    "misconceptions": [],
                    "hidden_hints": ["Look at checker.ts."],
                    "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    "concept_ids": ["validation_checking"],
                },
                "coverage_gaps": [],
            }
            (run_dir / "orchestration-result.json").write_text(
                json.dumps(
                    {
                        "response_payload": {
                            "metadata": {
                                "comprehension_plan": plan,
                                "understanding_checks": [
                                    {
                                        "id": "q1",
                                        "question": "Why does validation matter?",
                                        "expected_answer_points": ["It validates semantics."],
                                        "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                                    }
                                ],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            followup = type(
                "Followup",
                (),
                {
                    "to_dict": lambda self: {
                        "next_turn": "repair",
                        "markdown": "Repair the validation concept.",
                        "comprehension_state": {"current_teaching_stage": "repair"},
                    }
                },
            )()

            with patch(
                "services.retrieval.server.evaluate_answers",
                return_value=(
                    AnswerEvaluation(
                        question_id="q1",
                        status="partial",
                        matched_points=(),
                        missing_points=("It validates semantics.",),
                        feedback="Partial.",
                        next_turn="repair",
                        repair_focus="validation concept",
                    ),
                ),
            ), patch("services.retrieval.server.generate_followup", return_value=followup):
                output = state.evaluate_run_answers("run-1", {"answers": {"q1": "It checks things."}})

            self.assertEqual(output["comprehension_followup"]["next_turn"], "repair")
            self.assertTrue((run_dir / "comprehension-followup.json").exists())
            saved = json.loads((run_dir / "answer-evaluation.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["comprehension_followup"]["markdown"], "Repair the validation concept.")

    def test_safe_run_id_removes_path_characters(self) -> None:
        self.assertEqual(_safe_run_id("../bad run"), "bad-run")

    def test_github_repository_from_remote_url_parses_common_remote_shapes(self) -> None:
        self.assertEqual(_github_repository_from_remote_url("https://github.com/example/project.git"), "example/project")
        self.assertEqual(_github_repository_from_remote_url("git@github.com:example/project.git"), "example/project")
        self.assertEqual(_github_repository_from_remote_url("ssh://git@github.com/example/project.git"), "example/project")
        self.assertEqual(_github_repository_from_remote_url("https://gitlab.com/example/project.git"), "")

    def test_browse_workspace_returns_selected_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            selected = root / "project"
            selected.mkdir()
            state = RuntimeState(root)

            with patch("services.retrieval.server._choose_directory", return_value=selected):
                result = state.browse_workspace({"start_path": str(root)})

            self.assertEqual(result["workspace_root"], str(selected))
            self.assertFalse(result["cancelled"])

    def test_cgc_failure_message_reports_locked_database(self) -> None:
        message = _cgc_failure_message(
            {
                "stdout": "Database Connection Error: IO exception: Could not set lock on file : C:\\repo\\.codegraphcontext\\db\\kuzudb",
                "stderr": "",
            }
        )

        self.assertIn("database is locked", message)
        self.assertIn("Close other running retrieval/indexing jobs", message)

    def test_workspace_retrieval_config_uses_workspace_root_for_cgc(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            tool_root = root / "tool"
            (workspace / "src").mkdir(parents=True)
            tool_root.mkdir()
            (tool_root / ".env").write_text(VALID_ENV, encoding="utf-8")
            state = RuntimeState(workspace, tool_root=tool_root)

            config = state._workspace_retrieval_config(run_dir=workspace / ".guided-intelligence" / "index-prep")

            self.assertEqual(Path(config.cgc_repo_path or ""), workspace)
            self.assertEqual(Path(config.cgc_db_path), workspace / ".guided-intelligence" / "index" / "cgc-kuzu")

    def test_sync_cgcignore_writes_managed_excludes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / ".cgcignore").write_text("dist/\n", encoding="utf-8")

            _sync_cgcignore(workspace, ("node_modules", "coverage", "generated/file.ts"))

            raw = (workspace / ".cgcignore").read_text(encoding="utf-8")
            self.assertIn("dist/", raw)
            self.assertIn("node_modules/", raw)
            self.assertIn("coverage/", raw)
            self.assertIn("generated/file.ts", raw)


if __name__ == "__main__":
    unittest.main()
