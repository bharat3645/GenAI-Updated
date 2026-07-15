"""
ATS Agent Service — Multi-Agent Resume Analyzer.

6-Agent Architecture:
  1. Coordinator Agent   → Analyzes inputs, plans execution strategy
  2. Keyword Agent       → Skill/keyword extraction, gap analysis
  3. Format Agent        → ATS formatting compliance checks
  4. Content Agent       → Action verbs, quantifiable metrics, impact
  5. Job Matching Agent  → Semantic role/responsibility alignment
  6. Improvement Agent   → Targeted rewrite suggestions for weak points

Execution Model:
  - Coordinator runs first (planning phase)
  - Keyword, Format, Content, Job Matching run in parallel (analysis phase)
  - Improvement Agent runs after analysis (needs their outputs)
  - Scoring is computed programmatically (40% keyword, 30% format, 30% content)
  - Synthesis Agent aggregates all outputs into the final report
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from sse_starlette.sse import EventSourceResponse

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from shared.config import get_settings
from shared.llm_provider import LLMProvider
from shared.models import HealthResponse, ATSAnalyzeRequest, ATSReport, ATSScoreBreakdown

logger = logging.getLogger(__name__)
settings = get_settings()
llm = LLMProvider()
redis_client: aioredis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    redis_client = aioredis.from_url(settings.redis.url, decode_responses=True)
    yield
    await redis_client.aclose()


app = FastAPI(title="ATS Agent Service", version="2.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return HealthResponse(service="ats-agent-service")


# ── Agent Prompts ──────────────────────────────────────

COORDINATOR_PROMPT = """You are a resume analysis coordinator. Examine the resume and job description below, then produce an execution plan.

RESUME:
{resume}

JOB DESCRIPTION:
{job_description}

Assess the resume type (technical, managerial, creative, academic) and identify which analysis dimensions are most relevant. Determine if the resume appears to be plain-text or formatted.

Return JSON:
{{
  "resume_type": "technical|managerial|creative|academic|general",
  "is_plain_text": true,
  "priority_areas": ["list of most important analysis areas"],
  "initial_observations": "2-3 sentence overview of resume quality at first glance",
  "jd_key_requirements": ["top 5-8 core requirements from the JD"]
}}"""

KEYWORD_PROMPT = """Analyze this resume against the job description for keyword alignment.

RESUME:
{resume}

JOB DESCRIPTION:
{job_description}

COORDINATOR CONTEXT:
{coordinator_context}

Perform deep keyword analysis:
- Extract technical skills, tools, certifications, and domain terms from both documents
- Identify exact matches, partial matches, and semantic equivalents
- Flag critical missing keywords that would cause ATS rejection

Return JSON:
{{
  "keywords_found": ["list of matching keywords/skills found in resume"],
  "keywords_missing": ["list of important keywords from JD missing in resume"],
  "semantic_matches": ["pairs like 'resume: ML -> JD: Machine Learning'"],
  "keyword_relevance_score": <0-100 integer>,
  "analysis": "brief explanation of keyword alignment strength"
}}"""

FORMAT_PROMPT = """Analyze this resume's formatting for ATS compatibility.

RESUME:
{resume}

COORDINATOR CONTEXT:
{coordinator_context}

Check for:
- Tables or multi-column layouts (bad for ATS parsers)
- Graphics, images, or icon references
- Non-standard section headers (ATS expects: Contact, Summary, Experience, Education, Skills)
- Consistent date formatting (MM/YYYY or Month YYYY)
- Proper section ordering (Contact → Summary → Experience → Education → Skills)
- Bullet point consistency
- Font/encoding issues (special characters that break parsers)

Return JSON:
{{
  "formatting_issues": ["list of specific issues found"],
  "formatting_score": <0-100 integer>,
  "has_tables": false,
  "has_columns": false,
  "section_order_correct": true,
  "date_format_consistent": true,
  "analysis": "brief explanation"
}}"""

CONTENT_PROMPT = """Analyze this resume's content quality and impact.

RESUME:
{resume}

COORDINATOR CONTEXT:
{coordinator_context}

Check for:
- Action verbs starting bullet points (Achieved, Developed, Led, Implemented, etc.)
- Quantifiable metrics and results (percentages, dollar amounts, team sizes, timelines)
- Specific accomplishments vs vague descriptions ("increased revenue by 30%" vs "helped with sales")
- STAR method usage (Situation, Task, Action, Result)
- Relevance and impact of described experiences
- Weak bullet points that need improvement

Return JSON:
{{
  "action_verbs_found": ["list of action verbs used"],
  "quantifiable_metrics": ["list of metrics/numbers found"],
  "weak_bullets": ["list of vague or weak bullet points that need improvement"],
  "content_quality_score": <0-100 integer>,
  "content_suggestions": ["list of improvement suggestions"],
  "analysis": "brief explanation"
}}"""

JOB_MATCH_PROMPT = """Analyze how well this resume matches the job requirements semantically.

RESUME:
{resume}

JOB DESCRIPTION:
{job_description}

COORDINATOR CONTEXT:
{coordinator_context}

Go beyond keyword matching — assess:
- Does the candidate's experience level match the role's seniority?
- Do the described responsibilities align with the JD's requirements?
- Is the industry/domain experience relevant?
- Are there transferable skills that partially satisfy requirements?
- What are the strongest alignment points and biggest gaps?

Return JSON:
{{
  "job_match_score": <0-100 integer>,
  "match_details": ["specific alignment points between resume and JD"],
  "experience_gap": ["areas where resume falls short of JD requirements"],
  "transferable_strengths": ["skills/experience that partially satisfy unmet requirements"],
  "seniority_match": "under-qualified|matched|over-qualified",
  "analysis": "brief explanation of overall job fit"
}}"""

IMPROVEMENT_PROMPT = """You are a professional resume writer. Based on the analysis below, generate specific rewrite suggestions for the weakest parts of this resume.

RESUME:
{resume}

WEAK BULLETS IDENTIFIED:
{weak_bullets}

MISSING KEYWORDS:
{missing_keywords}

JOB DESCRIPTION CONTEXT:
{job_description}

For each weak bullet point, provide a specific, improved version that:
- Starts with a strong action verb
- Includes quantifiable metrics where possible
- Incorporates relevant missing keywords naturally
- Follows the STAR method (Situation, Task, Action, Result)

Return JSON:
{{
  "suggestions": [
    {{
      "original": "the original weak bullet text",
      "suggested_rewrite": "the improved version",
      "reason": "why this rewrite is better"
    }}
  ]
}}"""

SYNTHESIS_PROMPT = """Create a final ATS analysis report by aggregating all agent results.

COORDINATOR ASSESSMENT:
{coordinator_result}

KEYWORD ANALYSIS:
{keyword_result}

FORMAT ANALYSIS:
{format_result}

CONTENT ANALYSIS:
{content_result}

JOB MATCHING ANALYSIS:
{job_match_result}

IMPROVEMENT SUGGESTIONS:
{improvement_result}

COMPUTED SCORE: {computed_score} (weighted: 40% keyword + 30% formatting + 30% content)

Your job is to write a clear, actionable executive summary (3-5 sentences) covering:
- Overall ATS compatibility assessment
- Top 3 strengths
- Top 3 areas for immediate improvement
- Final recommendation

Return JSON:
{{
  "summary": "3-5 sentence executive summary with concrete recommendations"
}}"""


# ── Agent Execution ───────────────────────────────────

async def run_coordinator_agent(resume: str, job_description: str) -> dict:
    """Plan execution strategy based on resume type and JD."""
    prompt = COORDINATOR_PROMPT.format(resume=resume, job_description=job_description)
    return await llm.complete_json(prompt)


async def run_keyword_agent(resume: str, job_description: str, coordinator_ctx: str) -> dict:
    """Extract and compare keywords between resume and JD."""
    prompt = KEYWORD_PROMPT.format(
        resume=resume, job_description=job_description, coordinator_context=coordinator_ctx
    )
    return await llm.complete_json(prompt)


async def run_format_agent(resume: str, coordinator_ctx: str) -> dict:
    """Check resume formatting for ATS compatibility."""
    prompt = FORMAT_PROMPT.format(resume=resume, coordinator_context=coordinator_ctx)
    return await llm.complete_json(prompt)


async def run_content_agent(resume: str, coordinator_ctx: str) -> dict:
    """Analyze content quality — action verbs, metrics, impact."""
    prompt = CONTENT_PROMPT.format(resume=resume, coordinator_context=coordinator_ctx)
    return await llm.complete_json(prompt)


async def run_job_match_agent(resume: str, job_description: str, coordinator_ctx: str) -> dict:
    """Assess semantic alignment between resume and job requirements."""
    prompt = JOB_MATCH_PROMPT.format(
        resume=resume, job_description=job_description, coordinator_context=coordinator_ctx
    )
    return await llm.complete_json(prompt)


async def run_improvement_agent(
    resume: str, job_description: str,
    weak_bullets: list[str], missing_keywords: list[str],
) -> dict:
    """Generate targeted rewrite suggestions for weak bullet points."""
    if not weak_bullets:
        return {"suggestions": []}
    prompt = IMPROVEMENT_PROMPT.format(
        resume=resume,
        job_description=job_description,
        weak_bullets=json.dumps(weak_bullets),
        missing_keywords=json.dumps(missing_keywords),
    )
    return await llm.complete_json(prompt)


def compute_weighted_score(keyword_score: float, format_score: float, content_score: float) -> int:
    """Programmatic 40/30/30 weighted scoring — not LLM-estimated."""
    raw = (keyword_score * 0.40) + (format_score * 0.30) + (content_score * 0.30)
    return max(0, min(100, round(raw)))


async def run_synthesis_agent(
    coordinator_result: dict, keyword_result: dict, format_result: dict,
    content_result: dict, job_match_result: dict, improvement_result: dict,
    computed_score: int,
) -> dict:
    """Aggregate all findings into the executive summary."""
    prompt = SYNTHESIS_PROMPT.format(
        coordinator_result=json.dumps(coordinator_result, indent=2),
        keyword_result=json.dumps(keyword_result, indent=2),
        format_result=json.dumps(format_result, indent=2),
        content_result=json.dumps(content_result, indent=2),
        job_match_result=json.dumps(job_match_result, indent=2),
        improvement_result=json.dumps(improvement_result, indent=2),
        computed_score=computed_score,
    )
    return await llm.complete_json(prompt)


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely extract an integer from an agent result."""
    try:
        return max(0, min(100, int(val)))
    except (TypeError, ValueError):
        return default


def _safe_list(val: Any, default: list | None = None) -> list:
    """Safely extract a list from an agent result."""
    return val if isinstance(val, list) else (default or [])


def _build_report(
    coordinator_result: dict, keyword_result: dict, format_result: dict,
    content_result: dict, job_match_result: dict, improvement_result: dict,
    synthesis_result: dict,
) -> dict:
    """Assemble the final ATSReport from all agent outputs."""
    kw_score = _safe_int(keyword_result.get("keyword_relevance_score"))
    fmt_score = _safe_int(format_result.get("formatting_score"))
    cnt_score = _safe_int(content_result.get("content_quality_score"))
    jm_score = _safe_int(job_match_result.get("job_match_score"))
    weighted = compute_weighted_score(kw_score, fmt_score, cnt_score)

    return {
        "score": weighted,
        "breakdown": {
            "keyword_relevance": kw_score,
            "formatting_compliance": fmt_score,
            "content_quality": cnt_score,
            "job_match": jm_score,
            "weighted_score": weighted,
        },
        "keywords_found": _safe_list(keyword_result.get("keywords_found")),
        "keywords_missing": _safe_list(keyword_result.get("keywords_missing")),
        "formatting_issues": _safe_list(format_result.get("formatting_issues")),
        "content_suggestions": _safe_list(content_result.get("content_suggestions")),
        "action_verbs_found": _safe_list(content_result.get("action_verbs_found")),
        "quantifiable_metrics": _safe_list(content_result.get("quantifiable_metrics")),
        "job_match_details": _safe_list(job_match_result.get("match_details")),
        "improvement_suggestions": _safe_list(improvement_result.get("suggestions")),
        "summary": synthesis_result.get("summary", ""),
    }


# ── Endpoints ───────────────────────────────────────

@app.post("/analyze")
async def analyze(req: ATSAnalyzeRequest):
    """Run all 6 agents and return the final report."""
    task_id = str(uuid.uuid4())

    try:
        # Phase 1: Coordinator plans execution
        coordinator_result = await run_coordinator_agent(req.resume_text, req.job_description)
        coordinator_ctx = json.dumps(coordinator_result, indent=2)

        # Phase 2: Run 4 analysis agents in PARALLEL
        keyword_task = run_keyword_agent(req.resume_text, req.job_description, coordinator_ctx)
        format_task = run_format_agent(req.resume_text, coordinator_ctx)
        content_task = run_content_agent(req.resume_text, coordinator_ctx)
        job_match_task = run_job_match_agent(req.resume_text, req.job_description, coordinator_ctx)

        keyword_result, format_result, content_result, job_match_result = await asyncio.gather(
            keyword_task, format_task, content_task, job_match_task
        )

        # Phase 3: Improvement agent (needs content analysis output)
        weak_bullets = _safe_list(content_result.get("weak_bullets"))
        missing_keywords = _safe_list(keyword_result.get("keywords_missing"))
        improvement_result = await run_improvement_agent(
            req.resume_text, req.job_description, weak_bullets, missing_keywords
        )

        # Phase 4: Programmatic scoring + synthesis
        kw_score = _safe_int(keyword_result.get("keyword_relevance_score"))
        fmt_score = _safe_int(format_result.get("formatting_score"))
        cnt_score = _safe_int(content_result.get("content_quality_score"))
        computed_score = compute_weighted_score(kw_score, fmt_score, cnt_score)

        synthesis_result = await run_synthesis_agent(
            coordinator_result, keyword_result, format_result,
            content_result, job_match_result, improvement_result,
            computed_score,
        )

        report = _build_report(
            coordinator_result, keyword_result, format_result,
            content_result, job_match_result, improvement_result,
            synthesis_result,
        )

        # Cache report in Redis (1 hour TTL)
        await redis_client.setex(f"ats:report:{task_id}", 3600, json.dumps(report))

        return {"task_id": task_id, "report": report}
    except Exception as e:
        logger.exception("ATS analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/stream")
async def analyze_stream(req: ATSAnalyzeRequest):
    """SSE stream showing agent-by-agent progress through the 6-agent pipeline."""
    async def event_generator() -> AsyncIterator[dict]:
        # Phase 1: Coordinator
        yield {"data": json.dumps({"stage": "coordinator", "status": "running", "message": "Planning analysis strategy..."})}
        coordinator_result = await run_coordinator_agent(req.resume_text, req.job_description)
        yield {"data": json.dumps({"stage": "coordinator", "status": "done", "result": coordinator_result})}
        coordinator_ctx = json.dumps(coordinator_result, indent=2)

        # Phase 2: Parallel analysis agents
        yield {"data": json.dumps({"stage": "parallel_analysis", "status": "running", "message": "Running 4 agents in parallel: Keyword, Format, Content, Job Match..."})}

        keyword_result, format_result, content_result, job_match_result = await asyncio.gather(
            run_keyword_agent(req.resume_text, req.job_description, coordinator_ctx),
            run_format_agent(req.resume_text, coordinator_ctx),
            run_content_agent(req.resume_text, coordinator_ctx),
            run_job_match_agent(req.resume_text, req.job_description, coordinator_ctx),
        )

        yield {"data": json.dumps({"stage": "keyword", "status": "done", "result": keyword_result})}
        yield {"data": json.dumps({"stage": "format", "status": "done", "result": format_result})}
        yield {"data": json.dumps({"stage": "content", "status": "done", "result": content_result})}
        yield {"data": json.dumps({"stage": "job_match", "status": "done", "result": job_match_result})}

        # Phase 3: Improvement agent
        yield {"data": json.dumps({"stage": "improvement", "status": "running", "message": "Generating rewrite suggestions..."})}
        weak_bullets = _safe_list(content_result.get("weak_bullets"))
        missing_keywords = _safe_list(keyword_result.get("keywords_missing"))
        improvement_result = await run_improvement_agent(
            req.resume_text, req.job_description, weak_bullets, missing_keywords
        )
        yield {"data": json.dumps({"stage": "improvement", "status": "done", "result": improvement_result})}

        # Phase 4: Scoring + Synthesis
        kw_score = _safe_int(keyword_result.get("keyword_relevance_score"))
        fmt_score = _safe_int(format_result.get("formatting_score"))
        cnt_score = _safe_int(content_result.get("content_quality_score"))
        computed_score = compute_weighted_score(kw_score, fmt_score, cnt_score)

        yield {"data": json.dumps({"stage": "synthesis", "status": "running", "message": "Generating final report..."})}
        synthesis_result = await run_synthesis_agent(
            coordinator_result, keyword_result, format_result,
            content_result, job_match_result, improvement_result,
            computed_score,
        )

        report = _build_report(
            coordinator_result, keyword_result, format_result,
            content_result, job_match_result, improvement_result,
            synthesis_result,
        )
        yield {"data": json.dumps({"stage": "synthesis", "status": "done", "report": report})}

    return EventSourceResponse(event_generator())


@app.get("/report/{task_id}")
async def get_report(task_id: str):
    """Retrieve a cached report."""
    data = await redis_client.get(f"ats:report:{task_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Report not found or expired")
    return json.loads(data)
