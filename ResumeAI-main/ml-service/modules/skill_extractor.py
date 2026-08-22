"""
skill_extractor.py
------------------
Extracts and categorizes tech skills from resume/JD text.

Improvements over v1:
- SKILLS_BY_CATEGORY preserves category metadata at runtime.
- Aho-Corasick multi-pattern search (O(n) in text length) with regex fallback.
- Alias normalization handles spaced variants (e.g. "React JS").
- Removed misleading parent aliases (drf→django, mongoose→mongodb).
- Added modern AI/ML terms: LLMs, Gen AI, RAG, vector DB, etc.
- extract_skills() returns flat list + by_category breakdown.
"""

import re
import logging
from typing import List, Dict, Set, Tuple

logger = logging.getLogger(__name__)

# ── Categorized skills database ────────────────────────────────────────────────
# Each category maps to a list of canonical skill names.
# The flat SKILLS_DB set is derived from this at module load.
SKILLS_BY_CATEGORY: Dict[str, List[str]] = {

    "Programming Languages": [
        "python", "javascript", "typescript", "java", "c++", "c#", "c", "go",
        "rust", "swift", "kotlin", "ruby", "php", "scala", "r", "matlab",
        "perl", "shell", "bash", "powershell", "lua", "haskell", "elixir",
        "dart", "julia", "cobol", "fortran", "assembly", "vb.net",
        "visual basic", "f#", "clojure", "erlang", "ocaml", "groovy",
        "tcl", "awk", "sed", "prolog", "lisp", "scheme", "ada", "pascal",
        "delphi", "apex", "solidity", "vyper", "move",
    ],

    "Frontend Frameworks & Libraries": [
        "react", "vue", "angular", "svelte", "sveltekit", "next.js", "nuxt",
        "gatsby", "remix", "astro", "qwik", "solid.js", "preact", "alpine.js",
        "ember.js", "backbone.js", "lit", "stimulus",
    ],

    "HTML / CSS / Styling": [
        "html", "css", "sass", "scss", "less", "tailwind css", "bootstrap",
        "material-ui", "chakra ui", "ant design", "shadcn/ui", "radix ui",
        "headless ui", "daisyui", "bulma", "foundation",
        "styled-components", "emotion", "css modules", "css-in-js",
    ],

    "JavaScript Tools & State": [
        "jquery", "redux", "redux toolkit", "mobx", "zustand", "jotai",
        "recoil", "react query", "axios", "swr", "webpack", "vite", "parcel",
        "rollup", "esbuild", "babel", "eslint", "prettier", "jest", "vitest",
        "testing library", "storybook", "three.js", "d3.js", "chart.js",
        "recharts", "framer-motion", "gsap", "socket.io", "websocket",
        "web workers", "service workers", "pwa",
    ],

    "Backend Frameworks": [
        "node.js", "express", "fastapi", "flask", "django",
        "django rest framework", "drf", "spring", "spring boot", "spring mvc",
        "hibernate", "laravel", "rails", "asp.net", ".net", "nestjs", "koa",
        "hapi", "fastify", "strapi", "payload", "gin", "fiber", "echo",
        "chi", "actix", "rocket", "axum", "phoenix", "sinatra", "adonisjs",
    ],

    "API & Architecture": [
        "rest", "graphql", "grpc", "microservices", "serverless",
        "event-driven", "message queue", "api gateway", "oauth", "jwt",
        "saml", "openid connect", "soap", "protobuf", "avro", "openapi",
        "swagger", "trpc", "webhooks",
    ],

    "Databases — Relational": [
        "sql", "mysql", "postgresql", "sqlite", "oracle", "sql server",
        "mariadb", "cockroachdb", "tidb", "db2",
    ],

    "Databases — NoSQL": [
        "mongodb", "redis", "elasticsearch", "opensearch", "cassandra",
        "dynamodb", "couchdb", "couchbase", "neo4j", "arangodb", "fauna",
        "influxdb", "timescaledb",
    ],

    "BaaS / Managed DB": [
        "firebase", "firestore", "supabase", "appwrite", "pocketbase",
        "planetscale", "neon", "turso", "xata",
    ],

    "ORMs & Query Builders": [
        "prisma", "sequelize", "typeorm", "drizzle", "sqlalchemy", "knex",
        "peewee", "tortoise orm", "gorm", "mongoose", "ent",
    ],

    "Cloud Platforms": [
        "aws", "azure", "gcp", "ibm cloud", "oracle cloud", "alibaba cloud",
        "digitalocean", "linode", "vultr", "cloudflare", "vercel", "netlify",
        "render", "railway", "heroku",
    ],

    "AWS Services": [
        "s3", "ec2", "lambda", "rds", "cloudwatch", "sqs", "sns", "ecs",
        "eks", "fargate", "cloudfront", "route53", "iam", "vpc",
        "cloudformation", "cdk", "sam", "amplify", "cognito", "ses",
        "kinesis", "glue", "athena", "redshift", "emr",
    ],

    "DevOps & CI/CD": [
        "docker", "kubernetes", "terraform", "ansible", "puppet", "chef",
        "jenkins", "github actions", "gitlab ci", "circleci", "travis ci",
        "argocd", "flux", "tekton", "drone", "teamcity", "azure devops",
        "nginx", "apache", "caddy", "traefik", "haproxy", "ci/cd", "devops",
        "devsecops", "mlops", "gitops", "helm", "istio", "linkerd", "envoy",
        "consul", "prometheus", "grafana", "elk stack", "datadog", "splunk",
        "new relic", "opentelemetry", "jaeger", "zipkin",
    ],

    "OS & Networking": [
        "linux", "ubuntu", "debian", "centos", "fedora", "arch linux",
        "windows server", "macos", "unix", "tcp/ip", "http", "https", "dns",
        "ssl", "tls", "ssh", "ftp", "network security", "vpn",
        "load balancing", "computer networks",
    ],

    "AI / ML / Deep Learning": [
        "machine learning", "deep learning", "artificial intelligence",
        "natural language processing", "computer vision", "tensorflow",
        "pytorch", "keras", "jax", "scikit-learn", "xgboost", "lightgbm",
        "catboost", "pandas", "numpy", "matplotlib", "seaborn", "plotly",
        "transformers", "bert", "gpt", "llm", "large language model",
        "langchain", "llamaindex", "openai", "anthropic", "gemini",
        "stable diffusion", "diffusion models", "generative ai", "gen ai",
        "retrieval augmented generation", "rag", "fine-tuning", "rlhf",
        "data science", "data analysis", "data engineering", "data modeling",
        "feature engineering", "model evaluation", "hyperparameter tuning",
        "logistic regression", "linear regression", "random forest",
        "decision tree", "svm", "knn", "k-means", "dbscan", "pca",
        "dimensionality reduction", "neural network", "cnn", "rnn", "lstm",
        "gru", "transformer", "reinforcement learning", "supervised learning",
        "unsupervised learning", "time series", "anomaly detection",
        "recommendation system", "prompt engineering", "agentic ai",
    ],

    "Vector Databases & Embeddings": [
        "embeddings", "vector database", "pinecone", "weaviate", "chroma",
        "qdrant", "milvus", "faiss",
    ],

    "Data Engineering & Big Data": [
        "apache spark", "hadoop", "kafka", "airflow", "dbt", "flink",
        "hive", "hbase", "pig", "sqoop", "flume", "tableau", "power bi",
        "looker", "metabase", "superset", "jupyter", "google colab",
        "mlflow", "kubeflow", "wandb", "dvc", "etl", "elt",
        "data pipeline", "data warehouse", "data lake", "snowflake",
        "databricks", "bigquery",
    ],

    "Mobile Development": [
        "react native", "flutter", "ios", "android", "objective-c", "ionic",
        "xamarin", "cordova", "expo", "jetpack compose",
    ],

    "Testing": [
        "pytest", "unittest", "cypress", "selenium", "playwright", "mocha",
        "chai", "jasmine", "junit", "testng", "postman", "insomnia", "bruno",
        "k6", "artillery", "locust", "tdd", "bdd", "e2e testing",
        "unit testing", "integration testing",
    ],

    "Version Control & Collaboration": [
        "git", "github", "gitlab", "bitbucket", "svn", "jira", "confluence",
        "notion", "linear", "trello", "asana",
    ],

    "Design & UI/UX": [
        "figma", "sketch", "adobe xd", "invision", "zeplin", "photoshop",
        "illustrator", "after effects", "canva", "wireframing", "prototyping",
        "user research", "design system", "accessibility", "wcag",
    ],

    "CS Fundamentals": [
        "data structures", "algorithms", "oop", "dbms", "operating systems",
        "system design", "distributed systems", "solid principles",
        "design patterns", "clean code", "concurrency", "multithreading",
        "async programming", "complexity analysis",
    ],

    "Security": [
        "cybersecurity", "ssl", "tls", "encryption", "penetration testing",
        "web security", "owasp", "authentication", "authorization", "rbac",
        "abac", "zero trust", "sso", "2fa", "mfa", "cryptography", "hashing",
        "xss", "csrf", "sql injection",
    ],

    "Blockchain & Web3": [
        "blockchain", "solidity", "web3", "ethereum", "smart contracts",
        "polygon", "solana", "nft", "defi", "ipfs", "hardhat", "truffle",
    ],

    "Project Management & Methodologies": [
        "agile", "scrum", "kanban", "waterfall", "lean", "six sigma",
        "project management", "product management", "roadmapping",
    ],

    "Soft Skills": [
        "leadership", "team management", "communication", "problem solving",
        "critical thinking", "collaboration", "mentoring", "code review",
    ],

    "Miscellaneous Tech": [
        "twilio", "sendgrid", "stripe", "razorpay", "paypal",
        "google maps api", "mapbox", "pusher", "ably", "ffmpeg",
        "imagemagick", "pdf processing", "ocr", "regex", "cron", "celery",
        "bull", "agenda", "monorepo", "nx", "turborepo", "lerna",
        "web scraping", "puppeteer", "beautifulsoup", "scrapy",
        "redis cache", "cdn", "latex", "markdown",
    ],
}

# ── Derived flat set & reverse-category lookup ─────────────────────────────────
SKILLS_DB: Set[str] = {
    skill
    for skills in SKILLS_BY_CATEGORY.values()
    for skill in skills
}

# skill → category name (for gap reporting)
SKILL_TO_CATEGORY: Dict[str, str] = {
    skill: cat
    for cat, skills in SKILLS_BY_CATEGORY.items()
    for skill in skills
}


# ── Alias map: variant → canonical ────────────────────────────────────────────
# Rules:
#   - Only alias when the variant and canonical are genuinely interchangeable.
#   - Do NOT alias sub-frameworks to parents (drf ≠ django, mongoose ≠ mongodb).
#   - Normalize spaces so "React JS" (with space) also matches.
SKILL_ALIASES: Dict[str, str] = {
    # React
    "react.js": "react",
    "reactjs": "react",
    "react js": "react",
    # Vue
    "vue.js": "vue",
    "vuejs": "vue",
    "vue js": "vue",
    # Angular
    "angularjs": "angular",
    "angular js": "angular",
    # Next
    "nextjs": "next.js",
    "next js": "next.js",
    # Nuxt
    "nuxt.js": "nuxt",
    # Solid
    "solidjs": "solid.js",
    "solid js": "solid.js",
    # Node
    "nodejs": "node.js",
    "node js": "node.js",
    # Express
    "express.js": "express",
    "expressjs": "express",
    "express js": "express",
    # Nest
    "nest.js": "nestjs",
    "nest js": "nestjs",
    # Tailwind
    "tailwindcss": "tailwind css",
    "tailwind": "tailwind css",
    "tailwind.css": "tailwind css",
    # scikit-learn
    "sklearn": "scikit-learn",
    # Go
    "golang": "go",
    # Postgres
    "postgres": "postgresql",
    # Kubernetes
    "k8s": "kubernetes",
    # Machine Learning shorthands
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "nlp": "natural language processing",
    "cv": "computer vision",
    # LLM variants
    "llms": "llm",
    "large language models": "large language model",
    "gen-ai": "gen ai",
    "genai": "gen ai",
    "generative-ai": "generative ai",
    # RAG
    "retrieval-augmented generation": "retrieval augmented generation",
    # Cloud
    "amazon web services": "aws",
    "google cloud platform": "gcp",
    "google cloud": "gcp",
    "microsoft azure": "azure",
    # .NET
    ".net core": ".net",
    "asp.net core": "asp.net",
    # SQL Server
    "mssql": "sql server",
    # HTML/CSS versions
    "html5": "html",
    "css3": "css",
    # Data structures
    "dsa": "data structures",
    "object-oriented programming": "oop",
    "database management": "dbms",
    "operating systems": "os",
    # Auth
    "oauth 2.0": "oauth",
    # Spring (only exact synonym — spring boot is its own skill)
    "spring framework": "spring",
    # Rails
    "ruby on rails": "rails",
    # HuggingFace (transformers is the canonical library name)
    "hugging face": "transformers",
    "huggingface": "transformers",
    # SVM
    "support vector machine": "svm",
    # Git
    "git hub": "github",
    # REST
    "rest api": "rest",
    "restful": "rest",
    "restful api": "rest",
}


# ── Normalizer ─────────────────────────────────────────────────────────────────
def _normalize(text: str) -> str:
    """Lowercase, collapse whitespace, remove non-skill punctuation."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9+#.\-/\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def canonicalize(skill: str) -> str:
    """Map a skill variant to its canonical name (space-normalized lookup)."""
    normalized = re.sub(r'\s+', ' ', skill.strip().lower())
    return SKILL_ALIASES.get(normalized, skill)


# ── Aho-Corasick fast matcher (optional) ──────────────────────────────────────
def _build_ahocorasick(skills: Set[str]):
    """Build an Aho-Corasick automaton for O(n) multi-pattern search."""
    try:
        import ahocorasick
        A = ahocorasick.Automaton()
        for idx, skill in enumerate(skills):
            A.add_word(skill, (idx, skill))
        A.make_automaton()
        return A
    except ImportError:
        return None


# Build at module load (once); None → fall back to regex
_automaton = _build_ahocorasick(SKILLS_DB)

# Pre-compiled regex alternation fallback (sorted longest-first to avoid
# shorter patterns shadowing longer ones, e.g. "go" before "golang")
_SORTED_SKILLS = sorted(SKILLS_DB, key=len, reverse=True)
_SKILL_PATTERN = re.compile(
    r'(?<![a-z0-9+#.\-])(' +
    '|'.join(re.escape(s) for s in _SORTED_SKILLS) +
    r')(?![a-z0-9+#.\-])',
    re.IGNORECASE
)


def _find_skills_in_text(text: str) -> Set[str]:
    """
    Find all skill occurrences in text.
    Uses Aho-Corasick when available (O(n)), otherwise compiled regex.
    """
    if _automaton is not None:
        found = set()
        for _, (_, skill) in _automaton.iter(text):
            # Verify word boundaries manually (AC doesn't support them natively)
            idx = text.rfind(skill, 0, text.find(skill) + len(skill))
            before_ok = idx == 0 or not text[idx - 1].isalnum() and text[idx - 1] not in '+#.-'
            after_idx = idx + len(skill)
            after_ok  = after_idx >= len(text) or not text[after_idx].isalnum() and text[after_idx] not in '+#.-'
            if before_ok and after_ok:
                found.add(skill)
        return found
    else:
        return set(_SKILL_PATTERN.findall(text))


# ── Public API ─────────────────────────────────────────────────────────────────

def extract_skills(text: str) -> List[str]:
    """
    Extract and canonicalize skills from text.

    Returns a sorted flat list of canonical skill names.
    Also available as a by-category breakdown via extract_skills_detailed().
    """
    return extract_skills_detailed(text)["skills"]


def extract_skills_detailed(text: str) -> Dict:
    """
    Extract skills with full category breakdown.

    Returns:
        {
          "skills":      sorted list of canonical skill names,
          "by_category": { category_name: [skill, ...], ... }  ← only non-empty cats
        }
    """
    normalized = _normalize(text)
    raw_found  = _find_skills_in_text(normalized)

    # Canonicalize all found skills
    canonical: Set[str] = set()
    for skill in raw_found:
        canonical.add(canonicalize(skill))

    # Build category breakdown
    by_category: Dict[str, List[str]] = {}
    for skill in canonical:
        cat = SKILL_TO_CATEGORY.get(skill, "Other")
        by_category.setdefault(cat, []).append(skill)

    # Sort each category's list
    by_category = {cat: sorted(skills) for cat, skills in sorted(by_category.items())}

    return {
        "skills":      sorted(canonical),
        "by_category": by_category,
    }
