from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.conversation import Conversation, ConversationMode
from app.models.learner import Learner
from app.models.session import SessionRecord
from app.models.vocabulary import LearnerVocabulary, VocabularyItem

router = APIRouter()


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(db: AsyncSession = Depends(get_db)):
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

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quick Learn Admin</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 600px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #e0e0e0; }}
  th {{ color: #666; font-weight: 500; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  td {{ font-size: 1.1rem; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
</style>
</head>
<body>
<h1>Quick Learn &mdash; Dashboard</h1>
<table>
  <tr><th>Metric</th><th class="num">Value</th></tr>
  <tr><td>Total learners</td><td class="num">{total_learners}</td></tr>
  <tr><td>Total sessions</td><td class="num">{total_sessions}</td></tr>
  <tr><td>Average score</td><td class="num">{avg_score_display}</td></tr>
  <tr><td>Vocabulary items</td><td class="num">{total_vocab}</td></tr>
  <tr><td>Active sessions (lesson/review)</td><td class="num">{active_sessions}</td></tr>
  <tr><td>Learners active (last 7 days)</td><td class="num">{active_learners_7d}</td></tr>
</table>
</body>
</html>"""
    return HTMLResponse(content=html)
