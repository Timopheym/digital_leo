# digital_leo

## Langfuse

Credentials live in `.env` (gitignored): `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`.

Always invoke the CLI from the project root with `--env .env`, e.g.:

```bash
npx langfuse-cli --env .env api datasets create --name <name>
npx langfuse-cli --env .env api dataset-items create --dataset-name <name> --input '{"q":"..."}' --expected-output '{"a":"..."}'
```

Project: `digital_tolstoy` (org `timopheym`).


<claude-mem-context>
# Memory Context

# [digital_leo] recent context, 2026-05-04 3:38pm GMT+2

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (16,884t read) | 545,163t work | 97% savings

### May 4, 2026
S163 Create docs/task.md from Tolstoy_Digital.md — English task specification for Person NER & Linking in the Tolstoy Digital TEI corpus (May 4 at 2:21 PM)
S164 Research Tolstoy_Digital.md and set up digital_leo project locally for dual-approach person-NER evaluation — all 7 verification steps passed (May 4 at 2:40 PM)
S165 Corpus baseline investigation — confirming existing person markup scale, format, and distribution across the Tolstoy Digital TEI corpus (May 4 at 2:40 PM)
S168 Build and verify gold dataset pipeline for Tolstoy Digital TEI corpus Person NER &amp; Linking — final artifact verification and README documentation (May 4 at 2:41 PM)
S166 Install and connect Langfuse skills/MCP integration to Claude Code for the digital_leo project (May 4 at 2:56 PM)
S167 Build gold dataset pipeline for Tolstoy Digital TEI corpus Person NER & Linking project — from spec to working artifacts (May 4 at 2:56 PM)
S169 Install and connect the Langfuse skill for Claude Code in the digital_leo project (May 4 at 2:58 PM)
S170 Install and connect Langfuse skill for Claude Code in digital_leo — fully completed end-to-end (May 4 at 3:07 PM)
864 3:09p 🔵 personList.xml TEI Schema and Person Record Structure
865 " 🔵 Full TEI Reference Directory Contents in digital_leo
866 " 🔵 Existing Python PersonIndex Class in persons.py
867 " 🔵 personList.xml Contains 3,113 Person Records with 23 Distinct Category Tags
869 " ⚖️ Architecture Plan: Single-File Vanilla JS HTML Viewer for personList.xml
877 " 🔵 personList.xml structure in digital_leo repo
878 " ⚖️ Architecture decision: single self-contained HTML/JS viewer for personList.xml
868 " 🔵 2,568 of 3,113 Persons Have Image URLs; Three Note Types Per Person
871 3:11p 🔵 langfuse-cli projects subcommand — no "list", use "get-public"
872 " 🔵 Langfuse Auth Confirmed — Project Named "digital_tolstoy" Not "digital_leo"
873 " ✅ CLAUDE.md Created and Memory Updated with Langfuse Setup Docs
S171 Wire Langfuse tracing to approach_llm and approach_rules, upload gold datasets to Langfuse, and run experiments comparing both approaches with evaluation metrics (May 4 at 3:12 PM)
874 3:16p 🔵 digital_leo Project Structure and Dual-Approach Architecture
875 " 🔵 Core Modules: eval.py, approach_rules/matcher.py, and approach_llm/client.py Internals
876 " 🔵 Gold Dataset Schema and Project Configuration Details
879 3:17p 🔵 personList.xml persName ref attributes are pure Wikidata Q-IDs
880 3:19p 🟣 Created web/persons.html — single-file TEI person viewer
881 " 🟣 persons.html verified reachable via local HTTP server
882 " 🟣 persons.html inline JS passes Node.js syntax validation
883 " 🔵 Python PersonIndex loads 3,112 persons vs 3,113 in raw XML — one entry skipped
884 " 🔵 Smoke test of browser parsing logic against real XML confirmed coverage statistics
S172 Build a nice HTML/JS viewer to explore and look up personList.xml — completed and verified (May 4 at 3:20 PM)
885 3:21p 🔵 Langfuse Platform Capabilities Identified
886 " 🔵 Langfuse Python SDK Instrumentation Pattern
887 " 🔵 Langfuse Experiments Data Model for Evaluation
888 " 🔵 Langfuse Experiment Runner SDK API
889 " 🔵 Langfuse Evaluator Function Pattern
890 3:23p 🔵 run_experiment() API Parameters and Configuration
891 " 🔵 Low-Level Dataset API and Application Instrumentation
892 " 🔵 Langfuse CLI: dataset-items create Command
893 " 🔵 Langfuse CLI Schema: 28 API Resources Available
895 " 🔵 Langfuse CLI v0.0.9: Full Command Reference
896 " ✅ Langfuse and OpenAI Credentials Configured in .env
894 3:24p 🔵 dataset-items CLI Commands: CRUD Operations
897 " ✅ Added langfuse>=3.0 Python SDK Dependency
898 " ✅ Langfuse SDK and OpenTelemetry Dependencies Installed
899 3:25p ✅ Langfuse v4.5.1 Successfully Installed
900 " 🟣 Langfuse Tracing Environment Initialization Module
901 " 🟣 Langfuse Tracing Wired to approach_rules Runner
902 " 🟣 Instrumented Rule-Based Approach with @observe() Decorators
903 " 🟣 Added Langfuse Trace Flushing to Rules Runner Exit
904 " 🟣 Langfuse-Instrumented OpenAI Wrapper Integrated in LLM Approach
905 3:26p 🟣 Langfuse Tracing Wired to approach_llm Runner
906 " 🟣 Instrumented LLM Approach with Hierarchical @observe() Decorators
907 " ✅ LLM Runner Main Loop Refactored to Use Instrumented _process_file
908 " 🔵 Langfuse Integration Smoke Test Passed
909 3:34p 🔵 bibllist_bio.xml TEI Structure Analyzed
910 " 🔵 digital_leo Project Structure Mapped
911 3:35p 🔵 bibllist_bio.xml Scale and Data Distribution Confirmed
912 " 🔵 persons.html Architecture Patterns Fully Read
914 " 🟣 web/bibllist_bio.html Created — TEI Bibliography Explorer
913 " 🔵 8 Source Items in bibllist_bio.xml Fully Characterized

Access 545k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>