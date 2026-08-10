"""
Immediate mitigation suggestions for common production issues.

Focus: Stop the bleeding BEFORE root cause analysis.
"""

from typing import List, Dict


MITIGATION_PLAYBOOK = {
    "high_error_rate": {
        "immediate": [
            "🔄 Consider rollback to last known good version",
            "📈 Scale up instances/pods (horizontal scaling)",
            "🔌 Enable circuit breaker to prevent cascade failures",
            "🚦 Enable rate limiting to reduce load",
        ],
        "severity": "P0",
        "tti": "< 5 minutes",  # Time To Impact
    },
    
    "database_timeout": {
        "immediate": [
            "🔍 Check connection pool exhaustion (SHOW PROCESSLIST / pg_stat_activity)",
            "⏹️ Kill long-running queries",
            "🔄 Restart database connection pool",
            "📊 Increase connection pool size",
            "⚡ Add query timeout if missing",
        ],
        "severity": "P1",
        "tti": "< 10 minutes",
    },
    
    "memory_exhaustion": {
        "immediate": [
            "🚨 Identify memory-intensive process (top / htop)",
            "🔄 Restart affected service",
            "📈 Increase memory limits",
            "🗑️ Clear caches if applicable",
            "📊 Enable memory profiling for next occurrence",
        ],
        "severity": "P0",
        "tti": "< 2 minutes",
    },
    
    "api_timeout": {
        "immediate": [
            "⏱️ Increase timeout configuration",
            "🔍 Check external service status page",
            "🔄 Enable retry logic with exponential backoff",
            "🔌 Enable circuit breaker for external calls",
            "📊 Add timeout alerts",
        ],
        "severity": "P1",
        "tti": "< 10 minutes",
    },
    
    "disk_full": {
        "immediate": [
            "🗑️ Clear old logs (find /var/log -name '*.log' -mtime +7 -delete)",
            "📦 Clean package caches",
            "🔍 Identify large files (du -sh /* | sort -h)",
            "📈 Increase disk size",
            "🔄 Enable log rotation",
        ],
        "severity": "P0",
        "tti": "< 3 minutes",
    },
    
    "connection_refused": {
        "immediate": [
            "🔍 Check if service is running (ps aux | grep service_name)",
            "🔄 Restart service",
            "🌐 Verify network connectivity (ping, telnet)",
            "🔥 Check firewall rules",
            "📊 Check service health endpoint",
        ],
        "severity": "P1",
        "tti": "< 5 minutes",
    },
    
    "redis_timeout": {
        "immediate": [
            "🔍 Check Redis connection count (INFO clients)",
            "⏱️ Increase timeout setting",
            "🔄 Restart Redis client connection pool",
            "📊 Check Redis memory usage (INFO memory)",
            "🔌 Enable connection pooling if not present",
        ],
        "severity": "P1",
        "tti": "< 10 minutes",
    },
    
    "deployment_regression": {
        "immediate": [
            "⏮️ Rollback to previous version immediately",
            "📊 Compare current vs previous metrics",
            "🔍 Review recent commits for breaking changes",
            "🚨 Notify deployment team",
            "📝 Document what changed",
        ],
        "severity": "P0",
        "tti": "< 2 minutes",
    },
    
    "cascading_failure": {
        "immediate": [
            "🔌 Enable circuit breakers across all services",
            "🚦 Reduce traffic to affected service",
            "📈 Scale critical services",
            "🔄 Restart services in dependency order",
            "🚨 Page senior engineer immediately",
        ],
        "severity": "P0",
        "tti": "< 1 minute",
    },
}


def suggest_mitigations(
    error_patterns: Dict,
    severity: str,
    recent_deployment: bool = False
) -> Dict:
    """
    Suggest immediate mitigation steps based on error patterns.
    
    Args:
        error_patterns: Detected error patterns
        severity: P0/P1/P2/P3
        recent_deployment: Was there a recent deployment?
    
    Returns:
        Mitigation plan with immediate actions
    """
    mitigations = []
    matched_playbooks = []
    
    # Match error patterns to playbooks
    if error_patterns.get('http_errors', {}).get('5xx', 0) > 10:
        matched_playbooks.append("high_error_rate")
    
    if error_patterns.get('database_errors'):
        matched_playbooks.append("database_timeout")
    
    if error_patterns.get('memory_errors') or "memory" in str(error_patterns.get('exceptions', [])).lower():
        matched_playbooks.append("memory_exhaustion")
    
    if error_patterns.get('timeout_errors', 0) > 0:
        if 'redis' in str(error_patterns).lower():
            matched_playbooks.append("redis_timeout")
        else:
            matched_playbooks.append("api_timeout")
    
    if 'disk' in str(error_patterns.get('exceptions', [])).lower():
        matched_playbooks.append("disk_full")
    
    if 'connection refused' in str(error_patterns.get('exceptions', [])).lower():
        matched_playbooks.append("connection_refused")
    
    if recent_deployment and severity in ["P0", "P1"]:
        matched_playbooks.append("deployment_regression")
    
    # Check for cascading failure indicators
    if severity == "P0" and len(error_patterns.get('exceptions', [])) > 3:
        matched_playbooks.append("cascading_failure")
    
    # Collect all immediate actions
    for playbook_key in matched_playbooks:
        if playbook_key in MITIGATION_PLAYBOOK:
            playbook = MITIGATION_PLAYBOOK[playbook_key]
            mitigations.extend(playbook["immediate"])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_mitigations = []
    for m in mitigations:
        if m not in seen:
            seen.add(m)
            unique_mitigations.append(m)
    
    return {
        "immediate_actions": unique_mitigations,
        "matched_playbooks": matched_playbooks,
        "recommended_tti": _get_fastest_tti(matched_playbooks),
        "severity": severity,
    }


def _get_fastest_tti(playbook_keys: List[str]) -> str:
    """Get the most urgent TTI from matched playbooks."""
    ttis = []
    for key in playbook_keys:
        if key in MITIGATION_PLAYBOOK:
            tti = MITIGATION_PLAYBOOK[key]["tti"]
            ttis.append(tti)
    
    if not ttis:
        return "< 15 minutes"
    
    # Return the fastest (most urgent)
    return min(ttis)


def format_mitigation_plan(mitigation_plan: Dict) -> str:
    """Format mitigation plan for display."""
    if not mitigation_plan.get("immediate_actions"):
        return "[dim]No specific immediate actions suggested[/dim]"
    
    lines = [
        f"\n[bold red]⚠️ IMMEDIATE ACTIONS (Target: {mitigation_plan['recommended_tti']})[/bold red]",
        f"[yellow]Priority: {mitigation_plan['severity']} - Act BEFORE root cause analysis[/yellow]\n"
    ]
    
    for i, action in enumerate(mitigation_plan["immediate_actions"][:5], 1):
        lines.append(f"  {i}. {action}")
    
    if len(mitigation_plan["immediate_actions"]) > 5:
        remaining = len(mitigation_plan["immediate_actions"]) - 5
        lines.append(f"  [dim]... and {remaining} more actions[/dim]")
    
    if mitigation_plan.get("matched_playbooks"):
        lines.append(f"\n[dim]Matched playbooks: {', '.join(mitigation_plan['matched_playbooks'])}[/dim]")
    
    return '\n'.join(lines)


def get_rollback_command(project_type: str = "kubernetes") -> str:
    """Get rollback command based on deployment type."""
    commands = {
        "kubernetes": "kubectl rollout undo deployment/your-app",
        "docker": "docker service update --rollback your-service",
        "systemd": "systemctl restart your-service",
        "git": "git revert HEAD && git push origin main",
    }
    return commands.get(project_type, "# Rollback command depends on your deployment method")


def get_scaling_command(project_type: str = "kubernetes", scale_to: int = 5) -> str:
    """Get scaling command."""
    commands = {
        "kubernetes": f"kubectl scale deployment/your-app --replicas={scale_to}",
        "docker": f"docker service scale your-service={scale_to}",
        "aws": f"aws autoscaling set-desired-capacity --auto-scaling-group-name your-asg --desired-capacity {scale_to}",
    }
    return commands.get(project_type, f"# Scale to {scale_to} instances")
