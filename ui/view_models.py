from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BillingSummaryViewModel:
    billing_cycle: Optional[str] = None
    next_bill_date: Optional[str] = None
    next_price_estimate: Optional[str] = None


@dataclass
class SiteMetricViewModel:
    project_count: int = 0
    issue_count: int = 0
    unresolved_issue_count: int = 0
    updated_last_7_days_count: int = 0


@dataclass
class SiteUsersViewModel:
    total_users: Optional[int] = None
    active_users: Optional[int] = None
    inactive_users: Optional[int] = None


@dataclass
class SiteLicenceViewModel:
    licensed_users_estimate: Optional[int] = None
    seats: Optional[int] = None
    remaining_seats: Optional[int] = None
    licence_status: Optional[str] = None
    licence_api_access: Optional[str] = None


@dataclass
class SiteAuditViewModel:
    audit_status: Optional[str] = None
    audit_api_access: Optional[str] = None
    record_count: Optional[int] = None
    automation_related_record_count: Optional[int] = None
    category_counts: Dict[str, int] = field(default_factory=dict)


@dataclass
class SitePermissionsViewModel:
    overall_status: Optional[str] = None
    granted_count: int = 0
    denied_count: int = 0
    total_count: int = 0


@dataclass
class SiteSnapshotViewModel:
    collected_at: Optional[str] = None
    growth_status: Optional[str] = None
    delta_available: bool = False


@dataclass
class SiteServerInfoViewModel:
    server_title: Optional[str] = None
    deployment_type: Optional[str] = None
    version: Optional[str] = None
    default_locale: Optional[str] = None
    server_time_zone: Optional[str] = None
    display_url: Optional[str] = None


@dataclass
class SiteProjectSampleViewModel:
    key: str
    name: str
    project_type_key: Optional[str] = None
    style: Optional[str] = None
    simplified: Optional[bool] = None
    is_private: Optional[bool] = None


@dataclass
class SiteCardViewModel:
    site_key: str
    site_name: str
    site_url: str
    status: str

    metrics: SiteMetricViewModel = field(default_factory=SiteMetricViewModel)
    users: SiteUsersViewModel = field(default_factory=SiteUsersViewModel)
    licence: SiteLicenceViewModel = field(default_factory=SiteLicenceViewModel)
    audit: SiteAuditViewModel = field(default_factory=SiteAuditViewModel)
    permissions: SitePermissionsViewModel = field(default_factory=SitePermissionsViewModel)
    snapshot: SiteSnapshotViewModel = field(default_factory=SiteSnapshotViewModel)
    billing_summary: BillingSummaryViewModel = field(default_factory=BillingSummaryViewModel)
    server_info: SiteServerInfoViewModel = field(default_factory=SiteServerInfoViewModel)

    project_sample: List[SiteProjectSampleViewModel] = field(default_factory=list)

    usage_percent: Optional[int] = None
    last_collected: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HomepageSummaryViewModel:
    active_site_count: int = 0
    critical_count: int = 0
    warning_count: int = 0
    stable_count: int = 0
    total_projects: int = 0
    total_issues: int = 0
    total_unresolved: int = 0
    total_updated_last_7_days: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HomepageViewModel:
    title: str = "Jira Observation Monitor"
    subtitle: str = "Top-level operational view across active Jira sites"
    collected_at: Optional[str] = None
    active_site_count: int = 0

    summary: HomepageSummaryViewModel = field(default_factory=HomepageSummaryViewModel)

    critical_sites: List[SiteCardViewModel] = field(default_factory=list)
    warning_sites: List[SiteCardViewModel] = field(default_factory=list)
    stable_sites: List[SiteCardViewModel] = field(default_factory=list)

    site_tabs: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "collected_at": self.collected_at,
            "active_site_count": self.active_site_count,
            "summary": self.summary.to_dict(),
            "critical_sites": [site.to_dict() for site in self.critical_sites],
            "warning_sites": [site.to_dict() for site in self.warning_sites],
            "stable_sites": [site.to_dict() for site in self.stable_sites],
            "site_tabs": self.site_tabs,
        }