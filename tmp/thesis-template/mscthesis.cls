%% mscthesis.cls
%% UvA Software Engineering MSc Thesis document class
%% Requires LuaLaTeX on TeX Live 2025 or later

\NeedsTeXFormat{LaTeX2e}
\ProvidesExplClass{mscthesis}{2026/07/13}{2.0}
  {UvA~Software~Engineering~MSc~Thesis}

% ============================================================
% = Engine guard — this class requires LuaLaTeX
% ============================================================
\msg_new:nnn { mscthesis } { luatex-required }
  { This~class~requires~LuaLaTeX.~Please~recompile~with~lualatex. }

\sys_if_engine_luatex:F
  { \msg_fatal:nn { mscthesis } { luatex-required } }

% ============================================================
% = Class options — forward everything to memoir
% ============================================================
\PassOptionsToClass { a4paper, twoside, onecolumn, openright, 10pt } { memoir }
\DeclareOption* { \PassOptionsToClass { \CurrentOption } { memoir } }
\ProcessOptions \relax
\LoadClass { memoir }

% ============================================================
% = Page layout
% ============================================================
% \isopage
% \setlrmargins { 3.0cm } { * } { * }
% \checkandfixthelayout

% ============================================================
% = Fonts
% ============================================================
\RequirePackage{fontspec}
\setmainfont { Crimson~Pro } [ Numbers = { OldStyle, Proportional } ]
\setsansfont { PT~Sans      } [ Scale  = MatchLowercase ]
\setmonofont { Source~Code~Pro } [ Scale = MatchLowercase ]

% ============================================================
% = Chapter headings, page style, and structure
% ============================================================
\RequirePackage{graphicx}
\chapterstyle    { madsen    }
\pagestyle       { companion }
\settocdepth     { subsection }
\setsecnumdepth  { subsection }

% ============================================================
% = Epigraph style (memoir built-in)
% ============================================================
\setlength   { \epigraphwidth } { 8cm }
\setlength   { \epigraphrule  } { 0pt }
\epigraphposition     { center     }
\epigraphtextposition { flushleft  }
\epigraphsourceposition { flushright }
\renewcommand { \epigraphsize } { \itshape }

% ============================================================
% = Internal variables
% ============================================================
\ExplSyntaxOn

% --- metadata ---
\tl_new:N \l__mscthesis_subtitle_tl
\tl_new:N \l__mscthesis_university_tl

% --- committee: fixed roles ---
\tl_new:N \l__mscthesis_examinername_tl
\tl_new:N \l__mscthesis_examineraffil_tl
\tl_new:N \l__mscthesis_reviewername_tl
\tl_new:N \l__mscthesis_revieweraffil_tl
\tl_new:N \l__mscthesis_dailysupname_tl
\tl_new:N \l__mscthesis_dailysupaffil_tl
\tl_new:N \l__mscthesis_extsupname_tl
\tl_new:N \l__mscthesis_extsupaffil_tl

% --- committee: additional members ---
% Each item is \__mscthesis_member_row:nn{name}{affil}, ready to execute.
\seq_new:N \l__mscthesis_othermembers_seq
\bool_new:N \g__mscthesis_first_member_bool

% --- colophon ---
\bool_new:N \l__mscthesis_hascolophon_bool
\tl_new:N   \l__mscthesis_colophon_tl

% --- host organisation ---
\bool_new:N \l__mscthesis_hashostorg_bool
\tl_new:N   \l__mscthesis_hostorglogo_tl
\tl_new:N   \l__mscthesis_hostorg_tl

% --- cover picture ---
\bool_new:N \l__mscthesis_hascoverpic_bool
\tl_new:N   \l__mscthesis_coverpic_tl

% --- fixed strings ---
\tl_const:Nn \c__mscthesis_reptype_tl { MASTER~OF~SCIENCE  }
\tl_const:Nn \c__mscthesis_major_tl   { SOFTWARE~ENGINEERING }

\ExplSyntaxOff

% ============================================================
% = User-facing metadata commands
% ============================================================
\ExplSyntaxOn

\NewDocumentCommand \subtitle { m }
  { \tl_set:Nn \l__mscthesis_subtitle_tl {#1} }

\NewDocumentCommand \university { m }
  { \tl_set:Nn \l__mscthesis_university_tl {#1} }

\NewDocumentCommand \examiner { mm }
  {
    \tl_set:Nn \l__mscthesis_examinername_tl  {#1}
    \tl_set:Nn \l__mscthesis_examineraffil_tl {#2}
  }

\NewDocumentCommand \reviewer { mm }
  {
    \tl_set:Nn \l__mscthesis_reviewername_tl  {#1}
    \tl_set:Nn \l__mscthesis_revieweraffil_tl {#2}
  }

\NewDocumentCommand \dailysupervisor { mm }
  {
    \tl_set:Nn \l__mscthesis_dailysupname_tl  {#1}
    \tl_set:Nn \l__mscthesis_dailysupaffil_tl {#2}
  }

\NewDocumentCommand \externalsupervisor { mm }
  {
    \tl_set:Nn \l__mscthesis_extsupname_tl  {#1}
    \tl_set:Nn \l__mscthesis_extsupaffil_tl {#2}
  }

\NewDocumentCommand \othermember { mm }
  { \seq_put_right:Nn \l__mscthesis_othermembers_seq { {#1} {#2} } }

\NewDocumentCommand \colophon { m }
  {
    \bool_set_true:N \l__mscthesis_hascolophon_bool
    \tl_set:Nn \l__mscthesis_colophon_tl {#1}
  }

\NewDocumentCommand \hostorganisation { mm }
  {
    \bool_set_true:N \l__mscthesis_hashostorg_bool
    \tl_set:Nn \l__mscthesis_hostorglogo_tl {#1}
    \tl_set:Nn \l__mscthesis_hostorg_tl     {#2}
  }

\NewDocumentCommand \coverpicture { m }
  {
    \bool_set_true:N \l__mscthesis_hascoverpic_bool
    \tl_set:Nn \l__mscthesis_coverpic_tl {#1}
  }

\ExplSyntaxOff

% ============================================================
% = Default university block
% ============================================================
\university
  {
    \includegraphics
      [ height = 2cm, keepaspectratio ]
      { figures/msc-se-logo-small-white.png } \\[-4pt]
    \textsf { \Large Master~Software~Engineering } \\
    Informatics~Institute \\
    FNWI,~University~of~Amsterdam \\
    Amsterdam,~The~Netherlands
  }

% ============================================================
% = Month name helper
% ============================================================
\ExplSyntaxOn

\msg_new:nnn { mscthesis } { bad-month }
  { Invalid~month~number~'\the\month'. }

\cs_new:Npn \mscthesis_month_name:
  {
    \int_case:nnF { \c_sys_month_int }
      {
        {1}  { January   } {2}  { February  } {3}  { March     }
        {4}  { April     } {5}  { May       } {6}  { June      }
        {7}  { July      } {8}  { August    } {9}  { September }
        {10} { October   } {11} { November  } {12} { December  }
      }
      { \msg_error:nn { mscthesis } { bad-month } }
  }

\ExplSyntaxOff

% ============================================================
% = Default colophon — set at \begin{document} so \author
%   is already defined
% ============================================================
\ExplSyntaxOn

\hook_gput_code:nnn { begindocument } { mscthesis }
  {
    \bool_if:NF \l__mscthesis_hascolophon_bool
      {
        \tl_set:Nn \l__mscthesis_colophon_tl
          { \noindent Copyright~\textcopyright{}~\@author{},~\the\year{}. }
      }
  }

\ExplSyntaxOff

% ============================================================
% = Cover page (half-title)
% ============================================================
\ExplSyntaxOn

\NewDocumentCommand \makecoverpage {}
  {
    \thispagestyle { empty }
    \vspace* { \fill }
    \begin{flushright}
      { \Huge\sffamily \@title \par }
      \addvspace { 0.5em }
      \rule { \textwidth } { 4pt } \par
      \addvspace { 0.5em }
      \tl_if_empty:NF \l__mscthesis_subtitle_tl
        {
          { \Large\itshape \tl_use:N \l__mscthesis_subtitle_tl \par }
          \addvspace { 0.5em }
        }
      \vfill
      \bool_if:NT \l__mscthesis_hascoverpic_bool
        { \tl_use:N \l__mscthesis_coverpic_tl \vfill }
      { \Large \@author \par }
    \end{flushright}
    \vspace* { \fill }
    \clearpage
  }

\ExplSyntaxOff

% ============================================================
% = Formal title pages — internal helpers
% ============================================================
\ExplSyntaxOn

% Full-page minipage: top-aligned, textheight tall, content stretched.
\cs_new_protected:Npn \__mscthesis_fullpage_begin:
  { \noindent \begin{minipage} [t] [\textheight] [s] { \textwidth } }

\cs_new_protected:Npn \__mscthesis_fullpage_end:
  { \end{minipage} }

% Full-width horizontal rule.
\cs_new_protected:Npn \__mscthesis_hrule:n #1
  { \noindent \rule { \textwidth } {#1} \par }

% Optional committee row: suppressed when the name tl is empty.
\cs_new_protected:Npn \__mscthesis_committee_row:NNnn #1 #2 #3 #4
  % #1 name tl  #2 affil tl  #3 label text  #4 row terminator
  {
    \tl_if_empty:NF #1
      { #3 & \tl_use:N #1 \c_space_tl ( \tl_use:N #2 ) #4 }
  }

% Self-rendering row for \othermember entries.
% \bool_gset_false:N persists across the implicit groups of tabular cells
% and \seq_map_inline:Nn iterations.
\cs_new_protected:Npn \__mscthesis_member_row:nn #1 #2
  {
    \bool_if:NTF \g__mscthesis_first_member_bool
      { Other~members: } { }
    & #1 \c_space_tl ( #2 ) \\
    \bool_gset_false:N \g__mscthesis_first_member_bool
  }

% Emit all other-member rows; no-op when the sequence is empty.
\cs_new_protected:Npn \__mscthesis_othermembers_rows:
  {
    \seq_if_empty:NF \l__mscthesis_othermembers_seq
      {
        \bool_gset_true:N \g__mscthesis_first_member_bool
        \seq_map_inline:Nn \l__mscthesis_othermembers_seq
          {
            \__mscthesis_member_row:nn ##1
          }
      }
  }

\ExplSyntaxOff

% ============================================================
% = Formal title pages — page renderers
% ============================================================
\ExplSyntaxOn

% ---- Page 1: title ----
\cs_new_protected:Npn \__mscthesis_titlepage:
  {
    \thispagestyle { empty }
    \__mscthesis_fullpage_begin:
      \__mscthesis_hrule:n { 1.5pt }
      \vskip 1em
      \begin{center}
        { \Huge \@title \par }
        \vskip 1em
        \__mscthesis_hrule:n { 1.5pt }
        \vskip 2em
        { \large THESIS \par }
        \vskip 2em
        { \large
            submitted~in~partial~fulfilment~of~the \\
            requirements~for~the~degree~of
        \par }
        \vskip 2em
        { \large \tl_use:N \c__mscthesis_reptype_tl \par }
        \vskip 2em
        in
        \vskip 2em
        { \large \tl_use:N \c__mscthesis_major_tl \par }
        \vskip 2em
        by
        \vskip 2em
        { \large \@author \par }
        \vskip 2em
        under~the~supervision~of
        \vskip 0.5em
        { \large
            \tl_use:N \l__mscthesis_examinername_tl \c_space_tl
            ( \tl_use:N \l__mscthesis_examineraffil_tl )
        \par }
        \vskip 2.5em
        \mscthesis_month_name: \c_space_tl \the\year
      \end{center}
      \vfill
      \__mscthesis_footer:
    \__mscthesis_fullpage_end:
  }

% ---- Footer: university block left, host org right (if set) ----
\cs_new_protected:Npn \__mscthesis_footer:
  {
    \bool_if:NTF \l__mscthesis_hashostorg_bool
      { \__mscthesis_footer_split:   }
      { \__mscthesis_footer_centred: }
  }

\cs_new_protected:Npn \__mscthesis_footer_split:
  {
    \noindent
    \begin{tabular} { @{} l @{} r @{} }
      \begin{minipage} [b] { .54\textwidth }
        \tl_use:N \l__mscthesis_university_tl
      \end{minipage}
      &
      \begin{minipage} [b] { .46\textwidth }
        \begin{flushright}
          \includegraphics [ height = 2cm, keepaspectratio ]
            { \tl_use:N \l__mscthesis_hostorglogo_tl } \\
          \tl_use:N \l__mscthesis_hostorg_tl
        \end{flushright}
      \end{minipage}
    \end{tabular}
  }

\cs_new_protected:Npn \__mscthesis_footer_centred:
  { \begin{center} \tl_use:N \l__mscthesis_university_tl \end{center} }

% ---- Page 2: committee and colophon ----
\cs_new_protected:Npn \__mscthesis_committeepage:
  {
    \newpage
    \thispagestyle { empty }
    \__mscthesis_fullpage_begin:
      \noindent
      \begin{tabular} { @{} l p{.8\textwidth} @{} }
        \multicolumn{2} { @{}l@{} } { \emph { Thesis~Committee } } \\[1ex]
        Examiner~(chair):
          & \tl_use:N \l__mscthesis_examinername_tl \c_space_tl
            ( \tl_use:N \l__mscthesis_examineraffil_tl ) \\
        Second~Reviewer:
          & \tl_use:N \l__mscthesis_reviewername_tl \c_space_tl
            ( \tl_use:N \l__mscthesis_revieweraffil_tl ) \\
        \__mscthesis_committee_row:NNnn
          \l__mscthesis_dailysupname_tl \l__mscthesis_dailysupaffil_tl
          { Daily~Supervisor: } { \\ }
        \__mscthesis_committee_row:NNnn
          \l__mscthesis_extsupname_tl \l__mscthesis_extsupaffil_tl
          { External~Supervisor: } { \\ }
        \__mscthesis_othermembers_rows:
      \end{tabular}
      \vfill
      \begingroup
        \footnotesize
        \setlength { \parindent } { 0pt }
        \setlength { \parskip   } { \baselineskip }
        \tl_use:N \l__mscthesis_colophon_tl
      \endgroup
    \__mscthesis_fullpage_end:
  }

% ---- Public command ----
\NewDocumentCommand \makeformaltitlepages {}
  {
    \begingroup
      \let \footnotesize \small
      \let \footnoterule \relax
      \newpage
      \__mscthesis_titlepage:
      \__mscthesis_committeepage:
      \clearpage
    \endgroup
  }

\ExplSyntaxOff

% ============================================================
% = Epigraph page
% ============================================================
\ExplSyntaxOn

\NewDocumentCommand \makeepigraphpage { m }
  {
    \thispagestyle { empty }
    \vspace* { \fill }
    #1
    \vspace* { \fill }
    \clearpage
  }

\ExplSyntaxOff

% That's all, folks!
\endinput

% vim:ft=tex
