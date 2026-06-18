from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_FILE = BASE_DIR / 'latest_run_alerted.json'
DEFAULT_OUTPUT_FILE = BASE_DIR / 'latest_run_intelligence.json'
DEFAULT_OUTPUT_PRETTY_FILE = BASE_DIR / 'latest_run_intelligence_pretty.json'


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f'Input runtime file not found: {path}')
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise RuntimeError(f'Unable to read JSON from {path}: {exc}') from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f'Input payload is not a JSON object: {path}')
    return payload


def _save_json(path: Path, data: Dict[str, Any], indent: Optional[int] = None) -> None:
    path.write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding='utf-8')


def _risk(severity: str, scope: str, title: str, reason: str, value: Any = None, site_name: str = '', site_key: str = '') -> Dict[str, Any]:
    return {
        'severity': severity,
        'scope': scope,
        'title': title,
        'reason': reason,
        'value': value,
        'site_name': site_name,
        'site_key': site_key,
    }


def derive_intelligence(payload: Dict[str, Any]) -> Dict[str, Any]:
    estate = _safe_dict(payload.get('estate'))
    sites = [row for row in _safe_list(payload.get('sites')) if isinstance(row, dict)]
    runtime_alerts = _safe_dict(payload.get('runtime_alerts'))

    watchlist: List[Dict[str, Any]] = []
    top_risks: List[Dict[str, Any]] = []

    # Carry forward alert-derived risks first.
    for row in _safe_list(runtime_alerts.get('critical'))[:5]:
        if isinstance(row, dict):
            top_risks.append(dict(row))
    for row in _safe_list(runtime_alerts.get('warning'))[:5]:
        if isinstance(row, dict):
            top_risks.append(dict(row))

    disabled = _to_int(estate.get('managed_disabled_accounts'), 0)
    mfa_disabled = _to_int(estate.get('mfa_disabled_accounts'), 0)
    not_in_userbase = _to_int(estate.get('not_in_userbase_count'), 0)
    app_accounts = _to_int(estate.get('app_account_count'), 0)
    human_accounts = _to_int(estate.get('human_user_count'), 0)
    total_projects = _to_int(estate.get('total_projects'), 0)
    total_recent = _to_int(estate.get('total_recent_issues'), 0)

    if disabled > 0:
        watchlist.append(_risk('critical', 'estate', 'Managed disabled accounts', 'Managed disabled accounts require review in Atlassian Administration.', disabled))
    if mfa_disabled > 0:
        watchlist.append(_risk('warning', 'estate', 'MFA disabled accounts', 'Accounts with MFA disabled should be reviewed against security policy.', mfa_disabled))
    if not_in_userbase > 0:
        watchlist.append(_risk('warning', 'estate', 'Accounts not in userbase', 'Accounts flagged as not in the userbase should be understood and cleaned up where appropriate.', not_in_userbase))
    if human_accounts > 0 and app_accounts / max(human_accounts, 1) >= 0.50:
        watchlist.append(_risk('warning', 'estate', 'High app-account ratio', 'App/service identities are unusually high relative to human accounts.', app_accounts))
    if total_projects > 0 and total_recent == 0:
        watchlist.append(_risk('warning', 'estate', 'No recent issue activity', 'The estate shows zero issues updated in the last 7 days despite tracked projects.', total_recent))

    for site in sites:
        site_name = str(site.get('site_name') or site.get('name') or site.get('site') or 'site')
        site_key = str(site.get('site') or site.get('site_key') or '')
        projects = _to_int(site.get('project_count'), 0)
        recent = _to_int(site.get('issue_count_updated_last_7d'), 0)
        unresolved = _to_int(site.get('issue_count_unresolved'), 0)
        total_users = site.get('total_users')
        status = str(site.get('status') or '').strip().lower()
        reason = str(site.get('reason') or '').strip()

        if projects > 0 and recent == 0:
            watchlist.append(_risk('warning', 'site', f'No recent activity: {site_name}', 'Tracked projects exist but no recent issue updates were detected in the last 7 days.', recent, site_name, site_key))
        if projects > 0 and (total_users is None or _to_int(total_users, 0) == 0):
            watchlist.append(_risk('warning', 'site', f'No site user total: {site_name}', 'Site has tracked projects but user totals are missing or zero.', total_users, site_name, site_key))
        if unresolved >= 100:
            watchlist.append(_risk('critical', 'site', f'High unresolved backlog: {site_name}', 'Unresolved issue count is very high for this site.', unresolved, site_name, site_key))
        elif unresolved >= 25:
            watchlist.append(_risk('warning', 'site', f'Rising unresolved backlog: {site_name}', 'Unresolved issue count is elevated for this site.', unresolved, site_name, site_key))
        if status in {'critical', 'warning', 'degraded', 'caution'}:
            watchlist.append(_risk('warning' if status != 'critical' else 'critical', 'site', f'Site status flagged: {site_name}', reason or f'Site status is {status}.', unresolved, site_name, site_key))

    def severity_rank(item: Dict[str, Any]) -> int:
        sev = str(item.get('severity') or '').lower()
        return 2 if sev == 'critical' else 1 if sev == 'warning' else 0

    watchlist.sort(key=lambda item: (severity_rank(item), _to_int(item.get('value'), 0)), reverse=True)
    combined_top = (top_risks + watchlist)[:10]
    critical_count = len([r for r in watchlist if str(r.get('severity')).lower() == 'critical'])
    warning_count = len([r for r in watchlist if str(r.get('severity')).lower() == 'warning'])
    sites_with_risks = len({str(r.get('site_key')) for r in watchlist if str(r.get('site_key'))})
    estate_risk_score = critical_count * 10 + warning_count * 4
    operational_posture = 'Critical' if critical_count > 0 else 'Warning' if warning_count > 0 else 'Healthy'

    return {
        'generated_at_utc': _iso_now(),
        'analysed_sites_count': len(sites),
        'estate_risk_score': estate_risk_score,
        'sites_with_risks_count': sites_with_risks,
        'top_intelligence_risks_count': len(combined_top),
        'operational_posture': operational_posture,
        'top_risks': combined_top,
        'watchlist': watchlist,
        'critical_count': critical_count,
        'warning_count': warning_count,
    }


def apply_intelligence(payload: Dict[str, Any], intelligence: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload)
    data['intelligence_summary'] = {
        'estate_risk_score': intelligence.get('estate_risk_score', 0),
        'top_intelligence_risks_count': intelligence.get('top_intelligence_risks_count', 0),
        'sites_with_risks_count': intelligence.get('sites_with_risks_count', 0),
        'operational_posture': intelligence.get('operational_posture', 'Healthy'),
        'analysed_sites_count': intelligence.get('analysed_sites_count', 0),
        'top_risks': intelligence.get('top_risks', []),
    }
    data['intelligence_watchlist'] = intelligence.get('watchlist', [])

    drilldowns = _safe_dict(data.get('drilldowns'))
    drilldowns['intelligence::summary'] = {
        'title': 'Intelligence Summary',
        'reason': 'Operational intelligence derived from runtime estate, admin enrichment, and alert-rule outputs.',
        'atlassian_area': 'Operational intelligence',
        'columns': ['estate_risk_score', 'top_intelligence_risks_count', 'sites_with_risks_count', 'operational_posture', 'analysed_sites_count', 'critical_count', 'warning_count'],
        'rows': [{
            'estate_risk_score': intelligence.get('estate_risk_score', 0),
            'top_intelligence_risks_count': intelligence.get('top_intelligence_risks_count', 0),
            'sites_with_risks_count': intelligence.get('sites_with_risks_count', 0),
            'operational_posture': intelligence.get('operational_posture', 'Healthy'),
            'analysed_sites_count': intelligence.get('analysed_sites_count', 0),
            'critical_count': intelligence.get('critical_count', 0),
            'warning_count': intelligence.get('warning_count', 0),
        }],
    }
    drilldowns['intelligence::watchlist'] = {
        'title': 'Intelligence Watchlist',
        'reason': 'Current intelligence watchlist derived from alert signals and runtime heuristics.',
        'atlassian_area': 'Operational intelligence',
        'columns': ['severity', 'scope', 'site_name', 'title', 'reason', 'value'],
        'rows': intelligence.get('watchlist', []),
    }
    data['drilldowns'] = drilldowns
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description='Apply intelligence rules to the alerted runtime payload.')
    parser.add_argument('--input-file', default=str(DEFAULT_INPUT_FILE))
    parser.add_argument('--output-file', default=str(DEFAULT_OUTPUT_FILE))
    parser.add_argument('--output-pretty-file', default=str(DEFAULT_OUTPUT_PRETTY_FILE))
    args = parser.parse_args()
    try:
        payload = _load_json(Path(args.input_file))
        intelligence = derive_intelligence(payload)
        updated = apply_intelligence(payload, intelligence)
        _save_json(Path(args.output_file), updated, indent=None)
        _save_json(Path(args.output_pretty_file), updated, indent=2)
        print('Intelligence rules applied.')
        print(f"Estate risk score: {intelligence.get('estate_risk_score', 0)}")
        print(f"Analysed sites: {intelligence.get('analysed_sites_count', 0)}")
        print(f"Top intelligence risks: {intelligence.get('top_intelligence_risks_count', 0)}")
        print(f"Operational posture: {intelligence.get('operational_posture', 'Healthy')}")
        return 0
    except Exception as exc:
        print(f'ERROR: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
