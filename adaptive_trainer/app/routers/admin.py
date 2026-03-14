from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.models.conversation import Conversation, ConversationMode
from app.models.curriculum import CurriculumUnit, LearnerUnitProgress
from app.models.learner import Learner
from app.models.session import SessionRecord
from app.models.vocabulary import LearnerVocabulary, VocabularyItem

router = APIRouter()

RING_NAMES = ["Ring 0", "Ring 1", "Ring 2", "Ring 3", "Ring 4"]


def _check_admin_key(key: str = Query(alias="key", default="")) -> None:
    """Validate admin API key if one is configured."""
    if settings.admin_api_key and key != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_check_admin_key),
):
    # --- Aggregate stats ---
    total_learners = (await db.execute(select(func.count(Learner.id)))).scalar() or 0
    total_sessions = (await db.execute(select(func.count(SessionRecord.id)))).scalar() or 0
    avg_score = (await db.execute(select(func.avg(SessionRecord.avg_score)))).scalar()
    avg_score_display = f"{avg_score:.1f}" if avg_score is not None else "N/A"
    total_vocab = (await db.execute(select(func.count(VocabularyItem.id)))).scalar() or 0

    active_sessions = (
        await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.mode.in_([ConversationMode.lesson, ConversationMode.review, ConversationMode.gateway_test])
            )
        )
    ).scalar() or 0

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    active_learners_7d = (
        await db.execute(
            select(func.count(func.distinct(SessionRecord.learner_id))).where(
                SessionRecord.created_at >= seven_days_ago
            )
        )
    ).scalar() or 0

    # --- Per-learner stats ---
    learners_result = await db.execute(
        select(Learner.id, Learner.current_ring, Learner.last_session_date, Learner.current_streak)
        .order_by(Learner.id)
    )
    learners = learners_result.all()

    learner_ids = [row.id for row in learners]

    # Session stats per learner
    session_stats = {}
    if learner_ids:
        rows = (await db.execute(
            select(
                SessionRecord.learner_id,
                func.count(SessionRecord.id).label("count"),
                func.avg(SessionRecord.avg_score).label("avg"),
            )
            .where(SessionRecord.learner_id.in_(learner_ids))
            .group_by(SessionRecord.learner_id)
        )).all()
        for r in rows:
            session_stats[r.learner_id] = (r.count, r.avg)

    # Vocab stats per learner: total mastered + due for review
    vocab_stats = {}
    if learner_ids:
        today = date.today()
        rows = (await db.execute(
            select(
                LearnerVocabulary.learner_id,
                func.count(LearnerVocabulary.id).label("total"),
                func.count(case((LearnerVocabulary.due_date <= today, LearnerVocabulary.id))).label("due"),
            )
            .where(LearnerVocabulary.learner_id.in_(learner_ids))
            .group_by(LearnerVocabulary.learner_id)
        )).all()
        for r in rows:
            vocab_stats[r.learner_id] = (r.total, r.due)

    # Current unit per learner: most recent incomplete, or latest completed
    current_units: dict[int, str] = {}
    if learner_ids:
        # Get all progress entries with unit names
        rows = (await db.execute(
            select(
                LearnerUnitProgress.learner_id,
                CurriculumUnit.name,
                LearnerUnitProgress.completed_at,
                LearnerUnitProgress.started_at,
            )
            .join(CurriculumUnit, LearnerUnitProgress.unit_id == CurriculumUnit.id)
            .where(LearnerUnitProgress.learner_id.in_(learner_ids))
            .order_by(LearnerUnitProgress.started_at.desc())
        )).all()

        # Group by learner, pick first incomplete or first overall
        seen: set[int] = set()
        for r in rows:
            if r.learner_id in seen:
                continue
            if r.completed_at is None:
                current_units[r.learner_id] = r.name
                seen.add(r.learner_id)
        # For learners with all completed, pick the most recent
        for r in rows:
            if r.learner_id not in seen:
                current_units[r.learner_id] = f"{r.name} ✓"
                seen.add(r.learner_id)

    # Build per-learner rows
    learner_rows = []
    for idx, lr in enumerate(learners, 1):
        s_count, s_avg = session_stats.get(lr.id, (0, None))
        v_total, v_due = vocab_stats.get(lr.id, (0, 0))
        unit_name = current_units.get(lr.id, "—")
        last_active = lr.last_session_date.isoformat() if lr.last_session_date else ""
        last_active_display = lr.last_session_date.strftime("%Y-%m-%d") if lr.last_session_date else "Never"
        avg_pct = f"{s_avg * 100:.0f}%" if s_avg is not None else "—"

        learner_rows.append(
            f'<tr data-ring="{lr.current_ring}" data-last="{last_active}">'
            f"<td>Learner {idx}</td>"
            f'<td class="num">{RING_NAMES[lr.current_ring]}</td>'
            f"<td>{unit_name}</td>"
            f'<td class="num">{s_count}</td>'
            f'<td class="num">{avg_pct}</td>'
            f'<td class="num">{v_total}</td>'
            f'<td class="num">{v_due}</td>'
            f"<td>{last_active_display}</td>"
            f'<td class="num">{lr.current_streak}</td>'
            f"</tr>"
        )

    learner_table_body = "\n  ".join(learner_rows)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quick Learn Admin</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, sans-serif; max-width: 1100px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 24px; }}
  h2 {{ font-size: 1.1rem; margin: 32px 0 16px; color: #333; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #e0e0e0; white-space: nowrap; }}
  th {{ color: #666; font-weight: 500; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; cursor: default; }}
  td {{ font-size: 0.95rem; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  #aggregate {{ max-width: 420px; }}
  .controls {{ display: flex; gap: 16px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }}
  .controls label {{ font-size: 0.85rem; color: #555; }}
  .controls select {{ padding: 4px 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 0.85rem; }}
  th.sortable {{ cursor: pointer; user-select: none; }}
  th.sortable:hover {{ color: #111; }}
  th.sortable::after {{ content: " \\2195"; font-size: 0.7em; color: #aaa; }}
  th.sort-asc::after {{ content: " \\2191"; color: #111; }}
  th.sort-desc::after {{ content: " \\2193"; color: #111; }}
  tr.hidden {{ display: none; }}
</style>
</head>
<body>
<h1>Quick Learn &mdash; Dashboard</h1>

<table id="aggregate">
  <tr><th>Metric</th><th class="num">Value</th></tr>
  <tr><td>Total learners</td><td class="num">{total_learners}</td></tr>
  <tr><td>Total sessions</td><td class="num">{total_sessions}</td></tr>
  <tr><td>Average score</td><td class="num">{avg_score_display}</td></tr>
  <tr><td>Vocabulary items</td><td class="num">{total_vocab}</td></tr>
  <tr><td>Active sessions (lesson/review)</td><td class="num">{active_sessions}</td></tr>
  <tr><td>Learners active (last 7 days)</td><td class="num">{active_learners_7d}</td></tr>
</table>

<h2>Per-Learner Stats</h2>
<div class="controls">
  <label>Filter ring:
    <select id="ringFilter">
      <option value="all">All rings</option>
      <option value="0">Ring 0</option>
      <option value="1">Ring 1</option>
      <option value="2">Ring 2</option>
      <option value="3">Ring 3</option>
      <option value="4">Ring 4</option>
    </select>
  </label>
  <label>Sort by:
    <select id="sortField">
      <option value="id">Learner #</option>
      <option value="ring">Ring</option>
      <option value="lessons">Lessons</option>
      <option value="score">Avg Score</option>
      <option value="vocab">Vocab</option>
      <option value="due">Due</option>
      <option value="last">Last Active</option>
      <option value="streak">Streak</option>
    </select>
  </label>
  <label>
    <select id="sortDir">
      <option value="desc">Descending</option>
      <option value="asc">Ascending</option>
    </select>
  </label>
</div>

<table id="learnerTable">
  <thead>
    <tr>
      <th>Learner</th>
      <th class="num">Ring</th>
      <th>Current Unit</th>
      <th class="num">Lessons</th>
      <th class="num">Avg Score</th>
      <th class="num">Vocab</th>
      <th class="num">Due</th>
      <th>Last Active</th>
      <th class="num">Streak</th>
    </tr>
  </thead>
  <tbody>
  {learner_table_body}
  </tbody>
</table>

<script>
(function() {{
  const table = document.getElementById('learnerTable');
  const tbody = table.querySelector('tbody');
  const ringFilter = document.getElementById('ringFilter');
  const sortField = document.getElementById('sortField');
  const sortDir = document.getElementById('sortDir');

  function getVal(row, field) {{
    const cells = row.children;
    switch (field) {{
      case 'id': return parseInt(cells[0].textContent.replace('Learner ', '')) || 0;
      case 'ring': return parseInt(row.dataset.ring) || 0;
      case 'lessons': return parseInt(cells[3].textContent) || 0;
      case 'score': return parseInt(cells[4].textContent) || -1;
      case 'vocab': return parseInt(cells[5].textContent) || 0;
      case 'due': return parseInt(cells[6].textContent) || 0;
      case 'last': return row.dataset.last || '';
      case 'streak': return parseInt(cells[8].textContent) || 0;
      default: return 0;
    }}
  }}

  function applyView() {{
    const ring = ringFilter.value;
    const field = sortField.value;
    const asc = sortDir.value === 'asc';
    const rows = Array.from(tbody.querySelectorAll('tr'));

    rows.forEach(r => {{
      r.classList.toggle('hidden', ring !== 'all' && r.dataset.ring !== ring);
    }});

    rows.sort((a, b) => {{
      let va = getVal(a, field), vb = getVal(b, field);
      if (typeof va === 'string') return asc ? va.localeCompare(vb) : vb.localeCompare(va);
      return asc ? va - vb : vb - va;
    }});

    rows.forEach(r => tbody.appendChild(r));
  }}

  ringFilter.addEventListener('change', applyView);
  sortField.addEventListener('change', applyView);
  sortDir.addEventListener('change', applyView);
}})();
</script>
</body>
</html>"""
    return HTMLResponse(content=html)
