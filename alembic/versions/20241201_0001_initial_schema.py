"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2024-12-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # USERS
    # ==========================================================================
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=True),
        sa.Column('first_name', sa.String(100), nullable=True),
        sa.Column('last_name', sa.String(100), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('email_verified', sa.Boolean(), default=False),
        sa.Column('email_verification_token', sa.String(255), nullable=True),
        sa.Column('email_verification_sent_at', sa.DateTime(), nullable=True),
        sa.Column('password_reset_token', sa.String(255), nullable=True),
        sa.Column('password_reset_sent_at', sa.DateTime(), nullable=True),
        sa.Column('subscription_tier', sa.String(50), default='free'),
        sa.Column('stripe_customer_id', sa.String(255), nullable=True),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.Column('login_count', sa.String(50), default='0'),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_admin', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_stripe_customer_id', 'users', ['stripe_customer_id'])

    # ==========================================================================
    # SUBSCRIPTIONS
    # ==========================================================================
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(255), nullable=True),
        sa.Column('stripe_price_id', sa.String(255), nullable=True),
        sa.Column('tier', sa.String(50), nullable=False, default='free'),
        sa.Column('status', sa.String(50), nullable=False, default='active'),
        sa.Column('current_period_start', sa.DateTime(), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('billing_cycle', sa.String(20), default='monthly'),
        sa.Column('cancel_at_period_end', sa.String(5), default='false'),
        sa.Column('canceled_at', sa.DateTime(), nullable=True),
        sa.Column('trial_start', sa.DateTime(), nullable=True),
        sa.Column('trial_end', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_subscriptions_stripe_subscription_id', 'subscriptions', ['stripe_subscription_id'], unique=True)

    # ==========================================================================
    # USAGE TRACKING
    # ==========================================================================
    op.create_table(
        'usage_tracking',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('month', sa.DateTime(), nullable=False),
        sa.Column('alerts_sent', sa.Integer(), default=0),
        sa.Column('searches_performed', sa.Integer(), default=0),
        sa.Column('exports_performed', sa.Integer(), default=0),
        sa.Column('api_calls', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'month', name='uq_usage_user_month')
    )
    op.create_index('ix_usage_tracking_user_id', 'usage_tracking', ['user_id'])

    # ==========================================================================
    # OPPORTUNITIES
    # ==========================================================================
    op.create_table(
        'opportunities',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('notice_id', sa.String(100), nullable=False),
        sa.Column('solicitation_number', sa.String(100), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('notice_type', sa.String(100), nullable=True),
        sa.Column('posted_date', sa.Date(), nullable=True),
        sa.Column('response_deadline', sa.DateTime(), nullable=True),
        sa.Column('archive_date', sa.Date(), nullable=True),
        sa.Column('department_name', sa.String(255), nullable=True),
        sa.Column('agency_name', sa.String(255), nullable=True),
        sa.Column('office_name', sa.String(255), nullable=True),
        sa.Column('naics_code', sa.String(6), nullable=True),
        sa.Column('naics_description', sa.String(255), nullable=True),
        sa.Column('psc_code', sa.String(10), nullable=True),
        sa.Column('psc_description', sa.String(255), nullable=True),
        sa.Column('set_aside_type', sa.String(100), nullable=True),
        sa.Column('set_aside_description', sa.String(255), nullable=True),
        sa.Column('pop_city', sa.String(100), nullable=True),
        sa.Column('pop_state', sa.String(2), nullable=True),
        sa.Column('pop_zip', sa.String(10), nullable=True),
        sa.Column('pop_country', sa.String(3), nullable=True),
        sa.Column('contract_type', sa.String(100), nullable=True),
        sa.Column('award_number', sa.String(100), nullable=True),
        sa.Column('award_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('award_date', sa.Date(), nullable=True),
        sa.Column('awardee_name', sa.String(255), nullable=True),
        sa.Column('awardee_uei', sa.String(12), nullable=True),
        sa.Column('likelihood_score', sa.Integer(), default=50),
        sa.Column('score_reasons', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('ui_link', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), default='active'),
        sa.Column('raw_data', postgresql.JSONB(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_opportunities_notice_id', 'opportunities', ['notice_id'], unique=True)
    op.create_index('ix_opportunities_solicitation_number', 'opportunities', ['solicitation_number'])
    op.create_index('ix_opportunities_posted_date', 'opportunities', ['posted_date'])
    op.create_index('ix_opportunities_response_deadline', 'opportunities', ['response_deadline'])
    op.create_index('ix_opportunities_agency_name', 'opportunities', ['agency_name'])
    op.create_index('ix_opportunities_naics_code', 'opportunities', ['naics_code'])
    op.create_index('ix_opportunities_psc_code', 'opportunities', ['psc_code'])
    op.create_index('ix_opportunities_set_aside_type', 'opportunities', ['set_aside_type'])
    op.create_index('ix_opportunities_pop_state', 'opportunities', ['pop_state'])
    op.create_index('ix_opportunities_likelihood_score', 'opportunities', ['likelihood_score'])
    op.create_index('ix_opportunities_status', 'opportunities', ['status'])

    # ==========================================================================
    # POINTS OF CONTACT
    # ==========================================================================
    op.create_table(
        'points_of_contact',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('opportunity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('contact_type', sa.String(50), nullable=True),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('fax', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_points_of_contact_opportunity_id', 'points_of_contact', ['opportunity_id'])

    # ==========================================================================
    # ALERT PROFILES
    # ==========================================================================
    op.create_table(
        'alert_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('naics_codes', postgresql.ARRAY(sa.String(6)), nullable=True),
        sa.Column('psc_codes', postgresql.ARRAY(sa.String(10)), nullable=True),
        sa.Column('keywords', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('excluded_keywords', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('states', postgresql.ARRAY(sa.String(2)), nullable=True),
        sa.Column('countries', postgresql.ARRAY(sa.String(3)), nullable=True),
        sa.Column('set_aside_types', postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column('notice_types', postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column('min_score', sa.Integer(), default=0),
        sa.Column('min_value', sa.Numeric(15, 2), nullable=True),
        sa.Column('max_value', sa.Numeric(15, 2), nullable=True),
        sa.Column('agencies', postgresql.ARRAY(sa.String(255)), nullable=True),
        sa.Column('excluded_agencies', postgresql.ARRAY(sa.String(255)), nullable=True),
        sa.Column('alert_frequency', sa.String(20), default='daily'),
        sa.Column('alert_email', sa.String(255), nullable=True),
        sa.Column('alert_sms', sa.String(20), nullable=True),
        sa.Column('total_matches', sa.Integer(), default=0),
        sa.Column('last_match_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_alert_profiles_user_id', 'alert_profiles', ['user_id'])

    # ==========================================================================
    # ALERTS SENT
    # ==========================================================================
    op.create_table(
        'alerts_sent',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('alert_profile_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('opportunity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('delivery_method', sa.String(20), nullable=False),
        sa.Column('delivery_status', sa.String(20), default='pending'),
        sa.Column('email_message_id', sa.String(255), nullable=True),
        sa.Column('alert_type', sa.String(50), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('opened_at', sa.DateTime(), nullable=True),
        sa.Column('clicked_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['alert_profile_id'], ['alert_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_alerts_sent_user_id', 'alerts_sent', ['user_id'])
    op.create_index('ix_alerts_sent_alert_profile_id', 'alerts_sent', ['alert_profile_id'])
    op.create_index('ix_alerts_sent_opportunity_id', 'alerts_sent', ['opportunity_id'])

    # ==========================================================================
    # SAVED OPPORTUNITIES
    # ==========================================================================
    op.create_table(
        'saved_opportunities',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('opportunity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(50), default='saved'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('reminder_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'opportunity_id', name='uq_saved_user_opportunity')
    )
    op.create_index('ix_saved_opportunities_user_id', 'saved_opportunities', ['user_id'])
    op.create_index('ix_saved_opportunities_opportunity_id', 'saved_opportunities', ['opportunity_id'])

    # ==========================================================================
    # CONTRACT AWARDS (USAspending)
    # ==========================================================================
    op.create_table(
        'contract_awards',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('award_id', sa.String(100), nullable=False),
        sa.Column('piid', sa.String(50), nullable=True),
        sa.Column('parent_piid', sa.String(50), nullable=True),
        sa.Column('fain', sa.String(50), nullable=True),
        sa.Column('award_type', sa.String(20), nullable=False),
        sa.Column('award_type_description', sa.String(100), nullable=True),
        sa.Column('total_obligation', sa.Numeric(15, 2), nullable=True),
        sa.Column('base_and_all_options_value', sa.Numeric(15, 2), nullable=True),
        sa.Column('award_date', sa.Date(), nullable=True),
        sa.Column('period_of_performance_start', sa.Date(), nullable=True),
        sa.Column('period_of_performance_end', sa.Date(), nullable=True),
        sa.Column('naics_code', sa.String(6), nullable=True),
        sa.Column('naics_description', sa.String(255), nullable=True),
        sa.Column('psc_code', sa.String(10), nullable=True),
        sa.Column('psc_description', sa.String(255), nullable=True),
        sa.Column('awarding_agency_code', sa.String(10), nullable=True),
        sa.Column('awarding_agency_name', sa.String(255), nullable=True),
        sa.Column('awarding_sub_agency_code', sa.String(10), nullable=True),
        sa.Column('awarding_sub_agency_name', sa.String(255), nullable=True),
        sa.Column('awarding_office_code', sa.String(20), nullable=True),
        sa.Column('awarding_office_name', sa.String(255), nullable=True),
        sa.Column('funding_agency_code', sa.String(10), nullable=True),
        sa.Column('funding_agency_name', sa.String(255), nullable=True),
        sa.Column('recipient_uei', sa.String(12), nullable=True),
        sa.Column('recipient_name', sa.String(255), nullable=True),
        sa.Column('recipient_parent_uei', sa.String(12), nullable=True),
        sa.Column('recipient_parent_name', sa.String(255), nullable=True),
        sa.Column('recipient_city', sa.String(100), nullable=True),
        sa.Column('recipient_state', sa.String(2), nullable=True),
        sa.Column('recipient_zip', sa.String(10), nullable=True),
        sa.Column('recipient_country', sa.String(3), nullable=True),
        sa.Column('business_types', postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column('pop_city', sa.String(100), nullable=True),
        sa.Column('pop_state', sa.String(2), nullable=True),
        sa.Column('pop_zip', sa.String(10), nullable=True),
        sa.Column('pop_country', sa.String(3), nullable=True),
        sa.Column('pop_congressional_district', sa.String(5), nullable=True),
        sa.Column('competition_type', sa.String(50), nullable=True),
        sa.Column('number_of_offers', sa.Integer(), nullable=True),
        sa.Column('set_aside_type', sa.String(50), nullable=True),
        sa.Column('last_modified_date', sa.DateTime(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), nullable=True),
        sa.Column('raw_data', postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_contract_awards_award_id', 'contract_awards', ['award_id'], unique=True)
    op.create_index('ix_contract_awards_piid', 'contract_awards', ['piid'])
    op.create_index('ix_contract_awards_naics_code', 'contract_awards', ['naics_code'])
    op.create_index('ix_contract_awards_psc_code', 'contract_awards', ['psc_code'])
    op.create_index('ix_contract_awards_award_date', 'contract_awards', ['award_date'])
    op.create_index('ix_contract_awards_pop_end', 'contract_awards', ['period_of_performance_end'])
    op.create_index('ix_contract_awards_recipient_uei', 'contract_awards', ['recipient_uei'])
    op.create_index('ix_contract_awards_awarding_agency_name', 'contract_awards', ['awarding_agency_name'])
    op.create_index('ix_contract_awards_pop_state', 'contract_awards', ['pop_state'])

    # ==========================================================================
    # NAICS STATISTICS
    # ==========================================================================
    op.create_table(
        'naics_statistics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('naics_code', sa.String(6), nullable=False),
        sa.Column('naics_description', sa.String(255), nullable=True),
        sa.Column('total_awards_12mo', sa.Integer(), default=0),
        sa.Column('total_obligation_12mo', sa.Numeric(15, 2), default=0),
        sa.Column('avg_award_amount_12mo', sa.Numeric(15, 2), default=0),
        sa.Column('median_award_amount_12mo', sa.Numeric(15, 2), default=0),
        sa.Column('min_award_amount_12mo', sa.Numeric(15, 2), default=0),
        sa.Column('max_award_amount_12mo', sa.Numeric(15, 2), default=0),
        sa.Column('awards_under_25k', sa.Integer(), default=0),
        sa.Column('awards_25k_to_100k', sa.Integer(), default=0),
        sa.Column('awards_100k_to_250k', sa.Integer(), default=0),
        sa.Column('awards_250k_to_1m', sa.Integer(), default=0),
        sa.Column('awards_over_1m', sa.Integer(), default=0),
        sa.Column('small_business_awards', sa.Integer(), default=0),
        sa.Column('small_business_percentage', sa.Numeric(5, 2), default=0),
        sa.Column('avg_offers_received', sa.Numeric(4, 1), default=0),
        sa.Column('sole_source_percentage', sa.Numeric(5, 2), default=0),
        sa.Column('top_agencies', postgresql.JSONB(), nullable=True),
        sa.Column('top_recipients', postgresql.JSONB(), nullable=True),
        sa.Column('contracts_expiring_90_days', sa.Integer(), default=0),
        sa.Column('contracts_expiring_180_days', sa.Integer(), default=0),
        sa.Column('contracts_expiring_365_days', sa.Integer(), default=0),
        sa.Column('calculated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_naics_statistics_naics_code', 'naics_statistics', ['naics_code'], unique=True)

    # ==========================================================================
    # RECIPIENTS
    # ==========================================================================
    op.create_table(
        'recipients',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('uei', sa.String(12), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('parent_uei', sa.String(12), nullable=True),
        sa.Column('parent_name', sa.String(255), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(2), nullable=True),
        sa.Column('zip', sa.String(10), nullable=True),
        sa.Column('country', sa.String(3), default='USA'),
        sa.Column('business_types', postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column('is_small_business', sa.Boolean(), default=False),
        sa.Column('total_awards', sa.Integer(), default=0),
        sa.Column('total_obligation', sa.Numeric(15, 2), default=0),
        sa.Column('first_award_date', sa.Date(), nullable=True),
        sa.Column('last_award_date', sa.Date(), nullable=True),
        sa.Column('primary_naics_codes', postgresql.ARRAY(sa.String(6)), nullable=True),
        sa.Column('top_agencies', postgresql.JSONB(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_recipients_uei', 'recipients', ['uei'], unique=True)
    op.create_index('ix_recipients_state', 'recipients', ['state'])

    # ==========================================================================
    # RECOMPETE OPPORTUNITIES
    # ==========================================================================
    op.create_table(
        'recompete_opportunities',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('award_id', sa.String(100), nullable=False),
        sa.Column('piid', sa.String(50), nullable=False),
        sa.Column('period_of_performance_end', sa.Date(), nullable=False),
        sa.Column('naics_code', sa.String(6), nullable=True),
        sa.Column('total_value', sa.Numeric(15, 2), nullable=True),
        sa.Column('awarding_agency_name', sa.String(255), nullable=True),
        sa.Column('incumbent_name', sa.String(255), nullable=True),
        sa.Column('incumbent_uei', sa.String(12), nullable=True),
        sa.Column('status', sa.String(20), default='upcoming'),
        sa.Column('linked_opportunity_id', sa.String(100), nullable=True),
        sa.Column('watching_users', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_recompete_opportunities_award_id', 'recompete_opportunities', ['award_id'])
    op.create_index('ix_recompete_opportunities_pop_end', 'recompete_opportunities', ['period_of_performance_end'])
    op.create_index('ix_recompete_opportunities_naics_code', 'recompete_opportunities', ['naics_code'])

    # ==========================================================================
    # LABOR RATE CACHE
    # ==========================================================================
    op.create_table(
        'labor_rate_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('search_query', sa.String(255), nullable=False),
        sa.Column('experience_min', sa.Integer(), nullable=True),
        sa.Column('experience_max', sa.Integer(), nullable=True),
        sa.Column('education_level', sa.String(50), nullable=True),
        sa.Column('match_count', sa.Integer(), default=0),
        sa.Column('min_rate', sa.Numeric(8, 2), nullable=True),
        sa.Column('max_rate', sa.Numeric(8, 2), nullable=True),
        sa.Column('avg_rate', sa.Numeric(8, 2), nullable=True),
        sa.Column('median_rate', sa.Numeric(8, 2), nullable=True),
        sa.Column('percentile_25', sa.Numeric(8, 2), nullable=True),
        sa.Column('percentile_75', sa.Numeric(8, 2), nullable=True),
        sa.Column('sample_categories', postgresql.JSONB(), nullable=True),
        sa.Column('cached_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_labor_rate_cache_search_query', 'labor_rate_cache', ['search_query'])
    op.create_index('ix_labor_rate_cache_expires_at', 'labor_rate_cache', ['expires_at'])

    # ==========================================================================
    # COMMON JOB TITLES
    # ==========================================================================
    op.create_table(
        'common_job_titles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('display_title', sa.String(255), nullable=False),
        sa.Column('calc_search_terms', postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('typical_experience_min', sa.Integer(), nullable=True),
        sa.Column('typical_experience_max', sa.Integer(), nullable=True),
        sa.Column('typical_education', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_common_job_titles_display_title', 'common_job_titles', ['display_title'], unique=True)


def downgrade() -> None:
    op.drop_table('common_job_titles')
    op.drop_table('labor_rate_cache')
    op.drop_table('recompete_opportunities')
    op.drop_table('recipients')
    op.drop_table('naics_statistics')
    op.drop_table('contract_awards')
    op.drop_table('saved_opportunities')
    op.drop_table('alerts_sent')
    op.drop_table('alert_profiles')
    op.drop_table('points_of_contact')
    op.drop_table('opportunities')
    op.drop_table('usage_tracking')
    op.drop_table('subscriptions')
    op.drop_table('users')
