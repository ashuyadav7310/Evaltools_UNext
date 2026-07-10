from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth import AuthPrincipal
from database import Interview, Report, Test, get_db
from routes.deps import require_active_trainer_access

router = APIRouter()


def _serialize_report(report: Report, test_id: int | None = None, completed_at=None) -> dict:
    return {
        "id": report.id,
        "interviewId": report.interview_id,
        "testId": test_id,
        "candidateName": report.candidate_name,
        "testTitle": report.test_title,
        "totalScore": report.total_score,
        "maxScore": report.max_score,
        "scoreBreakdown": report.score_breakdown,
        "strengths": report.strengths,
        "weaknesses": report.weaknesses,
        "improvements": report.improvements,
        "overallJustification": report.overall_justification,
        "timeSpentSeconds": report.time_spent_seconds,
        "createdAt": report.created_at,
        "completedAt": completed_at,
    }


@router.get("/reports")
def list_reports(
    test_id: int | None = Query(default=None, alias="testId"),
    principal: AuthPrincipal = Depends(require_active_trainer_access),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Report, Interview.test_id, Interview.completed_at)
        .join(Interview, Interview.id == Report.interview_id)
        .join(Test, Test.id == Interview.test_id)
        .order_by(Report.created_at.desc())
    )
    if principal.role == "trainer":
        query = query.filter(Test.trainer_id == principal.trainer_id)
    if test_id is not None:
        query = query.filter(Interview.test_id == test_id)

    rows = query.all()
    return [
        _serialize_report(report, test_id=row_test_id, completed_at=completed_at)
        for report, row_test_id, completed_at in rows
    ]


@router.get("/reports/{interview_id}")
def get_report(
    interview_id: int,
    principal: AuthPrincipal = Depends(require_active_trainer_access),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Report)
        .join(Interview, Interview.id == Report.interview_id)
        .join(Test, Test.id == Interview.test_id)
        .filter(Report.interview_id == interview_id)
    )
    if principal.role == "trainer":
        query = query.filter(Test.trainer_id == principal.trainer_id)
    report = query.first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    interview = db.query(Interview).filter(Interview.id == report.interview_id).first()
    return _serialize_report(
        report,
        test_id=interview.test_id if interview else None,
        completed_at=interview.completed_at if interview else None,
    )
