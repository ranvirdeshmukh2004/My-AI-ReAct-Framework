"""
tools/ — Modular tool implementations
========================================
Shared infrastructure:
  - base.py       : Tool dataclass & ToolRegistry
  - common.py     : retrying HTTP, SSRF guard, ToolError, output shaping

Tools:
  - search_tool.py     : web + news search (site:/news:/recent: operators)
  - wikipedia_tool.py  : Wikipedia summaries with search fallback
  - url_reader_tool.py : page → clean Markdown (bs4, boilerplate stripped)
  - calculator_tool.py : sympy algebra, calculus, matrices, number theory
  - python_tool.py     : AST-validated sandboxed Python (numpy/pandas)
  - file_tool.py       : PDF/DOCX/XLSX/CSV/JSON/text reader, path-guarded
  - rag_search_tool.py : vector search over indexed documents
  - weather_tool.py    : current conditions via wttr.in
  - datetime_tool.py   : clocks, timezone conversion, date arithmetic
  - finance_tool.py    : stock/index/crypto quotes + currency conversion
  - convert_tool.py    : offline unit conversion across 11 dimensions
  - research_tool.py   : arXiv paper search + GitHub repository search
"""
