---
name: new-module
description: Scaffold a new pillar module directory with a Jupyter notebook and learning journal. Use when starting a new Medium article/agentic AI pillar exploration.
disable-model-invocation: true
---

The user wants to create a new module for exploring an agentic AI pillar. Arguments: $ARGUMENTS

## Instructions

1. **Parse the module name** from $ARGUMENTS. Convert it to a snake_case directory name (e.g., "Dynamic Memory Management" → `dynamic_memory_management`).

2. **Create the module directory** at the repo root: `<module_name>/`

3. **Create the Jupyter notebook** at `<module_name>/<module_name>.ipynb` with this structure:

   ```json
   {
    "cells": [
     {
      "cell_type": "markdown",
      "metadata": {},
      "source": ["# <Human-Readable Module Title>\n", "\n", "**Pillar:** <module name>\n", "**Date:** <today's date>\n", "**Article:** [Link when published]"]
     },
     {
      "cell_type": "code",
      "execution_count": null,
      "metadata": {},
      "outputs": [],
      "source": [
       "import os\n",
       "import time\n",
       "import operator\n",
       "from typing import TypedDict, Annotated, List, Dict, Any, Optional, Literal\n",
       "from concurrent.futures import Future, ThreadPoolExecutor\n",
       "\n",
       "from dotenv import load_dotenv\n",
       "load_dotenv()\n",
       "\n",
       "from pydantic import BaseModel, Field\n",
       "\n",
       "# LangChain messages\n",
       "from langchain_core.messages import (\n",
       "    HumanMessage, AIMessage, SystemMessage, ToolMessage, BaseMessage\n",
       ")\n",
       "from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder\n",
       "from langchain_core.tools import tool\n",
       "from langchain_core.language_models.chat_models import BaseChatModel\n",
       "\n",
       "# LangChain model providers\n",
       "from langchain_openai import ChatOpenAI\n",
       "from langchain_anthropic import ChatAnthropic\n",
       "from langchain_mistralai import ChatMistralAI\n",
       "from langchain_moonshot import ChatMoonshot\n",
       "\n",
       "# LangGraph\n",
       "from langgraph.graph import StateGraph, START, END\n",
       "from langgraph.graph.message import add_messages\n",
       "from langgraph.prebuilt import ToolNode, create_react_agent\n",
       "from langgraph.checkpoint.memory import MemorySaver\n",
       "from langgraph.types import Send\n",
       "\n",
       "# Verify required API keys\n",
       "assert os.getenv('OPENAI_API_KEY'), 'OPENAI_API_KEY not set'\n",
       "assert os.getenv('ANTHROPIC_API_KEY'), 'ANTHROPIC_API_KEY not set'\n",
       "assert os.getenv('MISTRAL_API_KEY'), 'MISTRAL_API_KEY not set'\n",
       "assert os.getenv('LANGSMITH_API_KEY'), 'LANGSMITH_API_KEY not set'"
      ]
     },
     {
      "cell_type": "code",
      "execution_count": null,
      "metadata": {},
      "outputs": [],
      "source": [
       "# LLM instances — one per provider\n",
       "llmOpenAI = ChatOpenAI(\n",
       "    model='gpt-5.4-mini',\n",
       "    temperature=0.0\n",
       ")\n",
       "\n",
       "llmAnthropic = ChatAnthropic(\n",
       "    model='claude-haiku-4-5',\n",
       "    temperature=0.0\n",
       ")\n",
       "\n",
       "llmMistral = ChatMistralAI(\n",
       "    model='mistral-medium-3-5',\n",
       "    temperature=0.0\n",
       ")\n",
       "\n",
       "llmMoonShot = ChatMoonshot(\n",
       "    model='kimi-k2.5',\n",
       "    temperature=1.0,\n",
       "    api_key=os.getenv('MOONSHOOT_API_KEY')\n",
       ")"
      ]
     }
    ],
    "metadata": {
     "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
     "language_info": {"name": "python", "version": "3.12.0"}
    },
    "nbformat": 4,
    "nbformat_minor": 5
   }
   ```

4. **Create the learning journal** at `<module_name>/learning.md` as a lean, content-ready file. Do NOT copy the "How to Use This Journal" or "AI Behaviour Instructions" blocks — those live in `concepts_learning_template.md` and are pasted in at session time. The file should contain ONLY:
   - A `# Concepts & Learning Journal` header with the module title, notebook name, and a one-line pointer to `../concepts_learning_template.md` for AI behaviour rules.
   - A single `# Journal Entry — <today's date>` section with empty Session Metadata table, TL;DR bullets, Business/Problem Statement, one Phase 1 skeleton, Open Questions, Next Experiments, Key Takeaways, Session Retrospective.
   - A `# Quick Entry — YYYY-MM-DD` section at the bottom.
   No instructional prose, no "What AI Will and Won't Do" table, no "How to Use" block.

5. **Report** the created files and remind the user to:
   - Update `_index.md` with a new session entry when they start working
   - Update `LEARNING_ROADMAP.md` to mark the article as in-progress
