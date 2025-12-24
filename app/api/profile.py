"""
Company Profile API endpoints.

Handles company profile management, NAICS codes, certifications,
past performance, capability statements, and onboarding flow.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import User
from app.models.company import (
    CompanyProfile,
    CompanyNAICS,
    CompanyCertification,
    PastPerformance,
    CapabilityStatement,
)
from app.schemas.company import (
    CompanyProfileCreate,
    CompanyProfileUpdate,
    CompanyProfileResponse,
    CompanyNAICSCreate,
    CompanyNAICSResponse,
    CompanyCertificationCreate,
    CompanyCertificationResponse,
    PastPerformanceCreate,
    PastPerformanceResponse,
    OnboardingStepUpdate,
    OnboardingStatusResponse,
    CapabilityStatementCreate,
    CapabilityStatementResponse,
)
from app.services.scoring_service import calculate_all_scores_for_user

router = APIRouter()


# =============================================================================
# Company Profile Endpoints
# =============================================================================

@router.get("/profile", response_model=Optional[CompanyProfileResponse])
async def get_company_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current user's company profile.
    Returns null if no profile exists (user hasn't completed onboarding).
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    return profile


@router.post("/profile", response_model=CompanyProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_company_profile(
    profile_data: CompanyProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create company profile (first step of onboarding).
    Only one profile per user allowed.
    """
    # Check if profile already exists
    existing = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company profile already exists. Use PATCH to update.",
        )

    # Create profile
    profile = CompanyProfile(
        user_id=current_user.id,
        onboarding_step=1,  # Step 1 complete (basic info)
        **profile_data.model_dump()
    )

    # Calculate initial completeness
    db.add(profile)
    db.commit()
    db.refresh(profile)

    profile.profile_completeness = profile.calculate_completeness()
    db.commit()
    db.refresh(profile)

    return profile


@router.patch("/profile", response_model=CompanyProfileResponse)
async def update_company_profile(
    profile_data: CompanyProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update company profile.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found. Create one first.",
        )

    # Update fields
    update_data = profile_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    # Recalculate completeness
    profile.profile_completeness = profile.calculate_completeness()

    db.commit()
    db.refresh(profile)

    # Always trigger scoring if user has at least one NAICS code
    naics_count = len(profile.naics_codes)
    if naics_count > 0:
        try:
            print(f"[SCORING] Triggering score recalculation after profile update for user {current_user.id}")
            result = calculate_all_scores_for_user(db, str(current_user.id))
            print(f"[SCORING] Profile update scoring complete: {result.get('scored', 0)} opportunities scored")
        except Exception as e:
            print(f"[SCORING ERROR] Failed to recalculate scores after profile update: {e}")
            import traceback
            traceback.print_exc()

    return profile


# =============================================================================
# NAICS Code Endpoints
# =============================================================================

@router.get("/profile/naics", response_model=List[CompanyNAICSResponse])
async def list_naics_codes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all NAICS codes for the company.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    return profile.naics_codes


@router.post("/profile/naics", response_model=CompanyNAICSResponse, status_code=status.HTTP_201_CREATED)
async def add_naics_code(
    naics_data: CompanyNAICSCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add a NAICS code to company profile.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found. Create profile first.",
        )

    # Check if NAICS code already exists
    existing = db.query(CompanyNAICS).filter(
        CompanyNAICS.company_profile_id == profile.id,
        CompanyNAICS.naics_code == naics_data.naics_code,
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"NAICS code {naics_data.naics_code} already exists",
        )

    # If this is set as primary, clear other primary flags
    if naics_data.is_primary:
        db.query(CompanyNAICS).filter(
            CompanyNAICS.company_profile_id == profile.id,
            CompanyNAICS.is_primary == True,
        ).update({"is_primary": False})

    naics = CompanyNAICS(
        company_profile_id=profile.id,
        **naics_data.model_dump()
    )

    db.add(naics)

    # Update onboarding step if needed
    if profile.onboarding_step < 2:
        profile.onboarding_step = 2
        profile.profile_completeness = profile.calculate_completeness()

    db.commit()
    db.refresh(naics)

    # Always trigger scoring when NAICS codes change (key input for personalization)
    try:
        print(f"[SCORING] Triggering score recalculation after NAICS add for user {current_user.id}")
        result = calculate_all_scores_for_user(db, str(current_user.id))
        print(f"[SCORING] NAICS add scoring complete: {result.get('scored', 0)} opportunities scored")
    except Exception as e:
        print(f"[SCORING ERROR] Failed to recalculate scores after NAICS update: {e}")
        import traceback
        traceback.print_exc()

    return naics


@router.delete("/profile/naics/{naics_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_naics_code(
    naics_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a NAICS code from company profile.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    naics = db.query(CompanyNAICS).filter(
        CompanyNAICS.id == naics_id,
        CompanyNAICS.company_profile_id == profile.id,
    ).first()

    if not naics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NAICS code not found",
        )

    db.delete(naics)
    profile.profile_completeness = profile.calculate_completeness()
    db.commit()

    # Always trigger scoring when NAICS codes change (if user still has any)
    remaining_naics = len(profile.naics_codes)
    if remaining_naics > 0:
        try:
            print(f"[SCORING] Triggering score recalculation after NAICS delete for user {current_user.id}")
            result = calculate_all_scores_for_user(db, str(current_user.id))
            print(f"[SCORING] NAICS delete scoring complete: {result.get('scored', 0)} opportunities scored")
        except Exception as e:
            print(f"[SCORING ERROR] Failed to recalculate scores after NAICS deletion: {e}")
            import traceback
            traceback.print_exc()


# =============================================================================
# Certification Endpoints
# =============================================================================

@router.get("/profile/certifications", response_model=List[CompanyCertificationResponse])
async def list_certifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all certifications for the company.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    return profile.certifications


@router.post("/profile/certifications", response_model=CompanyCertificationResponse, status_code=status.HTTP_201_CREATED)
async def add_certification(
    cert_data: CompanyCertificationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add a certification to company profile.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found. Create profile first.",
        )

    # Check if certification type already exists
    existing = db.query(CompanyCertification).filter(
        CompanyCertification.company_profile_id == profile.id,
        CompanyCertification.certification_type == cert_data.certification_type,
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Certification {cert_data.certification_type} already exists",
        )

    cert = CompanyCertification(
        company_profile_id=profile.id,
        **cert_data.model_dump()
    )

    db.add(cert)

    # Update onboarding step if needed
    if profile.onboarding_step < 3:
        profile.onboarding_step = 3
        profile.profile_completeness = profile.calculate_completeness()

    db.commit()
    db.refresh(cert)

    # Always trigger scoring when certifications change (affects eligibility score)
    if len(profile.naics_codes) > 0:
        try:
            print(f"[SCORING] Triggering score recalculation after cert add for user {current_user.id}")
            result = calculate_all_scores_for_user(db, str(current_user.id))
            print(f"[SCORING] Cert add scoring complete: {result.get('scored', 0)} opportunities scored")
        except Exception as e:
            print(f"[SCORING ERROR] Failed to recalculate scores after certification update: {e}")
            import traceback
            traceback.print_exc()

    return cert


@router.delete("/profile/certifications/{cert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_certification(
    cert_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a certification from company profile.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    cert = db.query(CompanyCertification).filter(
        CompanyCertification.id == cert_id,
        CompanyCertification.company_profile_id == profile.id,
    ).first()

    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certification not found",
        )

    db.delete(cert)
    profile.profile_completeness = profile.calculate_completeness()
    db.commit()

    # Always trigger scoring when certifications change (affects eligibility score)
    if len(profile.naics_codes) > 0:
        try:
            print(f"[SCORING] Triggering score recalculation after cert delete for user {current_user.id}")
            result = calculate_all_scores_for_user(db, str(current_user.id))
            print(f"[SCORING] Cert delete scoring complete: {result.get('scored', 0)} opportunities scored")
        except Exception as e:
            print(f"[SCORING ERROR] Failed to recalculate scores after certification deletion: {e}")
            import traceback
            traceback.print_exc()


# =============================================================================
# Past Performance Endpoints
# =============================================================================

@router.get("/profile/past-performance", response_model=List[PastPerformanceResponse])
async def list_past_performance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all past performance records.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    return profile.past_performances


@router.post("/profile/past-performance", response_model=PastPerformanceResponse, status_code=status.HTTP_201_CREATED)
async def add_past_performance(
    pp_data: PastPerformanceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add a past performance record.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found. Create profile first.",
        )

    pp = PastPerformance(
        company_profile_id=profile.id,
        **pp_data.model_dump()
    )

    db.add(pp)
    db.commit()
    db.refresh(pp)

    return pp


@router.delete("/profile/past-performance/{pp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_past_performance(
    pp_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a past performance record.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    pp = db.query(PastPerformance).filter(
        PastPerformance.id == pp_id,
        PastPerformance.company_profile_id == profile.id,
    ).first()

    if not pp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Past performance record not found",
        )

    db.delete(pp)
    db.commit()


# =============================================================================
# Onboarding Endpoints
# =============================================================================

@router.get("/onboarding/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current onboarding status.
    Used to determine if user needs to complete onboarding.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        return OnboardingStatusResponse(
            onboarding_completed=False,
            onboarding_step=0,
            profile_completeness=0,
            has_profile=False,
            has_naics=False,
            has_certifications=False,
        )

    return OnboardingStatusResponse(
        onboarding_completed=profile.onboarding_completed,
        onboarding_step=profile.onboarding_step,
        profile_completeness=profile.profile_completeness,
        has_profile=True,
        has_naics=len(profile.naics_codes) > 0,
        has_certifications=len(profile.certifications) > 0,
    )


@router.post("/onboarding/complete", response_model=CompanyProfileResponse)
async def complete_onboarding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark onboarding as complete.
    Called when user finishes the onboarding wizard.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found. Complete onboarding steps first.",
        )

    # Require at least basic profile and one NAICS code
    if len(profile.naics_codes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one NAICS code is required to complete onboarding.",
        )

    profile.onboarding_completed = True
    profile.onboarding_step = 5
    profile.profile_completeness = profile.calculate_completeness()

    db.commit()
    db.refresh(profile)

    # Trigger scoring recalculation for all opportunities
    try:
        calculate_all_scores_for_user(db, current_user.id)
    except Exception as e:
        # Log but don't fail the request - scoring can be retried
        print(f"Warning: Failed to calculate scores after onboarding: {e}")

    return profile


@router.post("/onboarding/skip")
async def skip_onboarding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Skip onboarding (user can complete later).
    Creates a minimal profile with just company name from user record.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if profile:
        # Profile exists, just mark as skipped
        profile.onboarding_completed = False
        profile.onboarding_step = -1  # -1 indicates skipped
        db.commit()
    else:
        # Create minimal profile
        profile = CompanyProfile(
            user_id=current_user.id,
            company_name=current_user.company_name or current_user.email.split("@")[0],
            onboarding_completed=False,
            onboarding_step=-1,
        )
        db.add(profile)
        db.commit()

    return {"message": "Onboarding skipped. You can complete your profile later in settings."}


# =============================================================================
# Scoring Endpoints
# =============================================================================

@router.post("/scoring/calculate")
async def calculate_scores(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually trigger score recalculation for all opportunities.
    Requires company profile with at least one NAICS code.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found. Create a profile first.",
        )

    # Check if user has NAICS codes (required for meaningful scoring)
    naics_count = db.query(CompanyNAICS).filter(
        CompanyNAICS.company_profile_id == profile.id
    ).count()

    if naics_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add at least one NAICS code to calculate personalized scores.",
        )

    try:
        result = calculate_all_scores_for_user(db, current_user.id)
        return {
            "message": "Scores calculated successfully",
            "opportunities_scored": result.get("scored", 0),
            "total_opportunities": result.get("total_opportunities", 0),
            "score_distribution": result.get("score_distribution"),
            "naics_count": result.get("naics_count", 0),
            "naics_codes": result.get("naics_codes", []),
            "cert_count": result.get("cert_count", 0),
            "certifications": result.get("certifications", []),
            "business_size": result.get("business_size"),
            "profile_completeness": result.get("profile_completeness", 0),
            "errors": result.get("errors"),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate scores: {str(e)}",
        )


@router.get("/scoring/debug")
async def debug_scoring(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Debug endpoint to check scoring data and diagnose issues.
    """
    from app.models.company import OpportunityScore
    from app.models import Opportunity

    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        return {
            "has_profile": False,
            "message": "No company profile found. Complete onboarding first.",
        }

    naics_codes = db.query(CompanyNAICS).filter(
        CompanyNAICS.company_profile_id == profile.id
    ).all()

    certifications = db.query(CompanyCertification).filter(
        CompanyCertification.company_profile_id == profile.id
    ).all()

    # Count existing scores
    score_count = db.query(OpportunityScore).filter(
        OpportunityScore.user_id == current_user.id
    ).count()

    # Get sample scores with opportunity details
    sample_scores = db.query(OpportunityScore).filter(
        OpportunityScore.user_id == current_user.id
    ).limit(5).all()

    # Get sample opportunities to compare NAICS
    sample_opps = db.query(Opportunity).filter(
        Opportunity.status == "active"
    ).limit(5).all()

    # Get user NAICS codes as list
    user_naics_list = [n.naics_code for n in naics_codes]

    return {
        "has_profile": True,
        "profile_id": str(profile.id),
        "user_id": str(current_user.id),
        "onboarding_completed": profile.onboarding_completed,
        "onboarding_step": profile.onboarding_step,
        "profile_completeness": profile.profile_completeness,
        "business_size": profile.business_size,
        "naics_codes": [
            {"code": n.naics_code, "is_primary": n.is_primary}
            for n in naics_codes
        ],
        "naics_codes_list": user_naics_list,
        "certifications": [
            {"type": c.certification_type, "active": c.is_active}
            for c in certifications
        ],
        "existing_scores_count": score_count,
        "sample_scores": [
            {
                "opportunity_id": str(s.opportunity_id),
                "overall_score": s.overall_score,
                "capability_score": s.capability_score,
                "capability_breakdown": s.capability_breakdown,
                "eligibility_score": s.eligibility_score,
                "eligibility_breakdown": s.eligibility_breakdown,
                "scale_score": s.scale_score,
                "timeline_score": s.timeline_score,
                "calculated_at": s.calculated_at.isoformat() if s.calculated_at else None,
            }
            for s in sample_scores
        ],
        "sample_opportunities": [
            {
                "id": str(o.id),
                "title": o.title[:50] if o.title else None,
                "naics_code": o.naics_code,
                "set_aside_type": o.set_aside_type,
                "contract_type": o.contract_type,
                "naics_match": o.naics_code in user_naics_list if o.naics_code else False,
                "naics_4digit_match": any(
                    o.naics_code[:4] == uc[:4] for uc in user_naics_list
                ) if o.naics_code and user_naics_list else False,
            }
            for o in sample_opps
        ],
    }


# =============================================================================
# Capability Statement Endpoints
# =============================================================================

@router.get("/profile/capability-statements", response_model=List[CapabilityStatementResponse])
async def list_capability_statements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all capability statements for the company.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    return profile.capability_statements


@router.post("/profile/capability-statements/upload", response_model=CapabilityStatementResponse)
async def upload_capability_statement(
    file: UploadFile = File(...),
    name: Optional[str] = None,
    is_default: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload and analyze a capability statement PDF or DOCX.

    The file will be analyzed using AI to extract:
    - Core competencies
    - Differentiators
    - Keywords for opportunity matching
    - Target NAICS codes (if mentioned)
    - Target agencies
    - Technologies and certifications mentioned

    After upload, scores will be recalculated to include the new keywords.
    """
    from app.services.capability_analysis_service import (
        analyze_capability_statement,
        extract_text_from_pdf,
        extract_text_from_docx,
    )

    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found. Create profile first.",
        )

    # Validate file type
    filename = file.filename or "unknown"
    file_ext = filename.lower().split(".")[-1] if "." in filename else ""

    if file_ext not in ["pdf", "docx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and DOCX files are supported. Received: " + file_ext,
        )

    # Read file content
    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file uploaded",
        )

    if len(file_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 10MB.",
        )

    # Extract text based on file type
    if file_ext == "pdf":
        text_content = extract_text_from_pdf(file_bytes, filename)
    else:  # docx
        text_content = extract_text_from_docx(file_bytes, filename)

    if not text_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract text from file. Please ensure the file contains readable text.",
        )

    # Analyze with Claude
    analysis = analyze_capability_statement(text_content, filename)

    if analysis.get("status") == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze capability statement: {analysis.get('error', 'Unknown error')}",
        )

    # If this is set as default, clear other default flags
    if is_default:
        db.query(CapabilityStatement).filter(
            CapabilityStatement.company_profile_id == profile.id,
            CapabilityStatement.is_default == True,
        ).update({"is_default": False})

    # Create capability statement record
    statement_name = name or analysis.get("company_name") or filename.rsplit(".", 1)[0]

    capability = CapabilityStatement(
        company_profile_id=profile.id,
        name=statement_name,
        full_text=text_content,
        core_competencies=analysis.get("core_competencies"),
        differentiators=analysis.get("differentiators"),
        keywords=analysis.get("keywords"),
        target_naics_codes=analysis.get("target_naics_codes"),
        target_agencies=analysis.get("target_agencies"),
        file_name=filename,
        is_default=is_default,
        is_active=True,
    )

    db.add(capability)
    db.commit()
    db.refresh(capability)

    # Trigger score recalculation if user has NAICS codes
    naics_count = len(profile.naics_codes)
    if naics_count > 0:
        try:
            print(f"[SCORING] Triggering score recalculation after capability statement upload for user {current_user.id}")
            result = calculate_all_scores_for_user(db, str(current_user.id))
            print(f"[SCORING] Capability upload scoring complete: {result.get('scored', 0)} opportunities scored")
        except Exception as e:
            print(f"[SCORING ERROR] Failed to recalculate scores after capability statement upload: {e}")
            import traceback
            traceback.print_exc()

    return capability


@router.post("/profile/capability-statements", response_model=CapabilityStatementResponse, status_code=status.HTTP_201_CREATED)
async def create_capability_statement(
    cap_data: CapabilityStatementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a capability statement manually (without file upload).
    Useful for entering capability data directly.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found. Create profile first.",
        )

    # If this is set as default, clear other default flags
    if cap_data.is_default:
        db.query(CapabilityStatement).filter(
            CapabilityStatement.company_profile_id == profile.id,
            CapabilityStatement.is_default == True,
        ).update({"is_default": False})

    capability = CapabilityStatement(
        company_profile_id=profile.id,
        **cap_data.model_dump()
    )

    db.add(capability)
    db.commit()
    db.refresh(capability)

    # Trigger score recalculation if user has NAICS codes
    naics_count = len(profile.naics_codes)
    if naics_count > 0:
        try:
            print(f"[SCORING] Triggering score recalculation after capability statement creation for user {current_user.id}")
            result = calculate_all_scores_for_user(db, str(current_user.id))
            print(f"[SCORING] Capability creation scoring complete: {result.get('scored', 0)} opportunities scored")
        except Exception as e:
            print(f"[SCORING ERROR] Failed to recalculate scores after capability statement creation: {e}")
            import traceback
            traceback.print_exc()

    return capability


@router.delete("/profile/capability-statements/{cap_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_capability_statement(
    cap_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a capability statement.
    """
    profile = db.query(CompanyProfile).filter(
        CompanyProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    capability = db.query(CapabilityStatement).filter(
        CapabilityStatement.id == cap_id,
        CapabilityStatement.company_profile_id == profile.id,
    ).first()

    if not capability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capability statement not found",
        )

    db.delete(capability)
    db.commit()

    # Trigger score recalculation if user has NAICS codes
    naics_count = len(profile.naics_codes)
    if naics_count > 0:
        try:
            print(f"[SCORING] Triggering score recalculation after capability statement deletion for user {current_user.id}")
            result = calculate_all_scores_for_user(db, str(current_user.id))
            print(f"[SCORING] Capability deletion scoring complete: {result.get('scored', 0)} opportunities scored")
        except Exception as e:
            print(f"[SCORING ERROR] Failed to recalculate scores after capability statement deletion: {e}")
            import traceback
            traceback.print_exc()
