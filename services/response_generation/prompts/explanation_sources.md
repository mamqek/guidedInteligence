# Explanation Prompt Techniques

The explanation prompt is grounded in these public writing and instructional-design sources:

- Write for the reader / audience-first framing  
  https://digital.gov/guides/plain-language/principles/write-for-reader/

- Bottom line first; organize in logical order; put important information first  
  https://digital.gov/guides/plain-language/principles/organize/

- Headings that orient scanning; question headings when they match reader questions  
  https://digital.gov/guides/plain-language/design/headings/

- Short sentences, short sections, one topic per paragraph  
  https://digital.gov/guides/plain-language/writing/clear-short/

- Conversational tone, active voice, simple headings, chunked content  
  https://digital.gov/resources/plain-language-web-writing-tips/

- Worked-example style guidance for novice learners  
  Van Gog & Paas, Cognitive Load Theory: Advances in Research on Worked Examples, Animations, and Cognitive Load Measurement  
  https://link.springer.com/article/10.1007/s10648-010-9145-4

The grounding and anti-hallucination rules are based on these prompt/RAG sources:

- Strong instruction hierarchy, clear task framing, and using provided context as the reference material  
  OpenAI, Prompt Engineering Guide  
  https://developers.openai.com/api/docs/guides/prompt-engineering

- Explicit handling of grounded context, uncertainty, and validation rather than treating prompt wording as evidence  
  Microsoft, Prompt engineering concepts for Azure OpenAI / Foundry  
  https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/prompt-engineering

- Iterative validation of RAG answers against retrieved evidence to detect unsupported claims  
  AWS, Detect hallucinations for RAG-based systems  
  https://aws.amazon.com/blogs/machine-learning/detect-hallucinations-for-rag-based-systems/

This prompt also applies those sources to a code-explanation setting in a specific way:

- The explanation is prose-first, because the reader needs a mental model of the system before they can use code excerpts well.
- Retrieved snippets are treated as evidence and implementation anchors, not as the primary output.
- The explanation should connect behavior to subsystem responsibility and likely modification points when the evidence supports that conclusion.
- The explanation must treat retrieved snippets as the source of truth. If the user's requested feature terms are absent from the snippets, the response must say what is not shown instead of filling the gap from general knowledge or the prompt text.
- Grounding quality is checked iteratively with real retrieved examples, because prompt wording alone is not enough to prevent RAG drift.
