├── app/                         # Main Application Source Code
│   ├── api/                     # API Route Handlers
│   │   └── v1/                  # Versioned API (v1 endpoints)
│   ├── core/                    # Core Application Config & Logic
│   │   ├── langgraph/           # AI Agent / LangGraph Logic
│   │   │   └── tools/           # Agent Tools (search, actions, etc.)
│   │   └── prompts/             # AI System & Agent Prompts
│   ├── models/                  # Database Models (SQLModel)
│   ├── schemas/                 # Data Validation Schemas (Pydantic)
│   ├── services/                # Business Logic Layer
│   └── utils/                   # Shared Helper Utilities
├── evals/                       # AI Evaluation Framework
│   └── metrics/                 # Evaluation Metrics & Criteria
│       └── prompts/             # LLM-as-a-Judge Prompt Definitions
├── grafana/                     # Grafana Observability Configuration
│   └── dashboards/              # Grafana Dashboards
│       └── json/                # Dashboard JSON Definitions
├── prometheus/                  # Prometheus Monitoring Configuration
├── scripts/                     # DevOps & Local Automation Scripts
│   └── rules/                   # Project Rules for Cursor
└── .github/                     # GitHub Configuration
    └── workflows/               # GitHub Actions CI/CD Workflows


This directory structure might seem complex to you at first but we are following a generic best-practice pattern that is used in many agentic systems or even in pure software engineering. Each folder has a specific purpose:

app/: Contains the main application code, including API routes, core logic, database models, and utility functions.
evals/: Houses the evaluation framework for assessing AI performance using various metrics and prompts
grafana/ and prometheus/: Store configuration files for monitoring and observability tools.
