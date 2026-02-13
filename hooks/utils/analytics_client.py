"""
Analytics and performance monitoring client.
Provides access to performance reports, bottleneck analysis, and quality assessment.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import time

try:
    from .config_loader import get_config
except ImportError:
    from config_loader import get_config


class AnalyticsClient:
    """
    Client for performance analysis and system monitoring.

    Supports:
    - Performance reporting
    - Bottleneck analysis
    - Token usage tracking
    - Quality assessment
    - System diagnostics
    """

    def __init__(self, timeout: Optional[float] = None):
        """
        Initialize analytics client.

        Args:
            timeout: Operation timeout in seconds
        """
        self.config = get_config()
        self.timeout = timeout or self.config.get_timeout('analytics')
        self.log_dir = self.config.get_log_dir()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / 'analytics_client.jsonl'

    def _log(self, operation: str, params: Dict, result: Any, success: bool, elapsed: float):
        """Log analytics operation."""
        try:
            entry = {
                'timestamp': datetime.now().isoformat(),
                'operation': operation,
                'params': {k: str(v)[:100] for k, v in params.items()},
                'success': success,
                'elapsed_ms': round(elapsed * 1000, 2)
            }
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception:
            pass

    def _call_tool(self, tool_name: str, params: Dict, timeout: Optional[float] = None) -> Optional[Dict]:
        """Call MCP tool via subprocess."""
        if not self.config.is_feature_enabled('analytics'):
            return None

        use_timeout = timeout or self.timeout

        start_time = time.time()
        try:
            cmd = ['npx', 'claude-flow@alpha', 'mcp', 'call', tool_name, json.dumps(params)]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=use_timeout,
                cwd=str(Path.home())
            )

            elapsed = time.time() - start_time

            if result.returncode == 0 and result.stdout.strip():
                try:
                    parsed = json.loads(result.stdout.strip())
                    self._log(tool_name, params, parsed, True, elapsed)
                    return parsed
                except json.JSONDecodeError:
                    self._log(tool_name, params, result.stdout.strip(), True, elapsed)
                    return {'raw_output': result.stdout.strip()}
            else:
                self._log(tool_name, params, result.stderr, False, elapsed)
                return None

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            self._log(tool_name, params, 'TIMEOUT', False, elapsed)
            return None
        except Exception as e:
            elapsed = time.time() - start_time
            self._log(tool_name, params, str(e), False, elapsed)
            return None

    # =========================================================================
    # PERFORMANCE ANALYSIS
    # =========================================================================

    def performance_report(self, timeframe: str = '24h',
                           format: str = 'summary') -> Optional[Dict]:
        """
        Generate performance report with real-time metrics.

        Args:
            timeframe: Report timeframe (24h, 7d, 30d)
            format: Report format (summary, detailed, json)

        Returns:
            Performance report
        """
        return self._call_tool('performance_report', {
            'timeframe': timeframe,
            'format': format
        })

    def bottleneck_analyze(self, component: Optional[str] = None,
                           metrics: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Identify performance bottlenecks.

        Args:
            component: Specific component to analyze
            metrics: Metrics to check

        Returns:
            Bottleneck analysis result
        """
        params = {}
        if component:
            params['component'] = component
        if metrics:
            params['metrics'] = metrics
        return self._call_tool('bottleneck_analyze', params)

    def trend_analysis(self, metric: str, period: str = '7d') -> Optional[Dict]:
        """
        Analyze performance trends over time.

        Args:
            metric: Metric to analyze
            period: Time period

        Returns:
            Trend analysis result
        """
        return self._call_tool('trend_analysis', {
            'metric': metric,
            'period': period
        })

    def benchmark_run(self, suite: Optional[str] = None,
                      iterations: int = 10) -> Optional[Dict]:
        """
        Execute performance benchmarks.

        Args:
            suite: Benchmark suite (all, wasm, swarm, agent, task)
            iterations: Number of iterations

        Returns:
            Benchmark results
        """
        params = {'iterations': iterations}
        if suite:
            params['suite'] = suite
        return self._call_tool('benchmark_run', params)

    # =========================================================================
    # TOKEN & COST ANALYSIS
    # =========================================================================

    def token_usage(self, operation: Optional[str] = None,
                    timeframe: str = '24h') -> Optional[Dict]:
        """
        Analyze token consumption.

        Args:
            operation: Specific operation to analyze
            timeframe: Time period

        Returns:
            Token usage analysis
        """
        params = {'timeframe': timeframe}
        if operation:
            params['operation'] = operation
        return self._call_tool('token_usage', params)

    def cost_analysis(self, timeframe: str = '24h') -> Optional[Dict]:
        """
        Analyze resource costs.

        Args:
            timeframe: Time period

        Returns:
            Cost analysis result
        """
        return self._call_tool('cost_analysis', {'timeframe': timeframe})

    # =========================================================================
    # QUALITY ASSESSMENT
    # =========================================================================

    def quality_assess(self, target: str, criteria: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Run quality assessment on a target.

        Args:
            target: Assessment target (session, task, code, etc.)
            criteria: Quality criteria to check

        Returns:
            Quality assessment result
        """
        params = {'target': target}
        if criteria:
            params['criteria'] = criteria
        return self._call_tool('quality_assess', params)

    def error_analysis(self, logs: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Analyze error patterns.

        Args:
            logs: Log entries to analyze

        Returns:
            Error analysis result
        """
        params = {}
        if logs:
            params['logs'] = logs
        return self._call_tool('error_analysis', params)

    # =========================================================================
    # METRICS & STATISTICS
    # =========================================================================

    def metrics_collect(self, components: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Collect system metrics.

        Args:
            components: Components to collect metrics from

        Returns:
            Collected metrics
        """
        params = {}
        if components:
            params['components'] = components
        return self._call_tool('metrics_collect', params)

    def usage_stats(self, component: Optional[str] = None) -> Optional[Dict]:
        """
        Get usage statistics.

        Args:
            component: Specific component

        Returns:
            Usage statistics
        """
        params = {}
        if component:
            params['component'] = component
        return self._call_tool('usage_stats', params)

    # =========================================================================
    # HEALTH & DIAGNOSTICS
    # =========================================================================

    def health_check(self, components: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Check system health.

        Args:
            components: Components to check

        Returns:
            Health check result
        """
        params = {}
        if components:
            params['components'] = components
        return self._call_tool('health_check', params)

    def diagnostic_run(self, components: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Run system diagnostics.

        Args:
            components: Components to diagnose

        Returns:
            Diagnostic results
        """
        params = {}
        if components:
            params['components'] = components
        return self._call_tool('diagnostic_run', params)

    def log_analysis(self, log_file: str, patterns: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Analyze log file for patterns.

        Args:
            log_file: Log file path
            patterns: Patterns to search for

        Returns:
            Log analysis result
        """
        params = {'logFile': log_file}
        if patterns:
            params['patterns'] = patterns
        return self._call_tool('log_analysis', params)

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def is_available(self) -> bool:
        """Check if analytics services are available."""
        try:
            result = self.health_check()
            return result is not None
        except Exception:
            return False


# Convenience function
def get_analytics_client(timeout: Optional[float] = None) -> AnalyticsClient:
    """Get an analytics client instance."""
    return AnalyticsClient(timeout=timeout)
