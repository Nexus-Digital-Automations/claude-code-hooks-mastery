"""
Workflow automation and pipeline management client.
Supports workflow creation, SPARC methodology, and parallel execution.
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


class WorkflowClient:
    """
    Client for workflow automation and SPARC operations.

    Supports:
    - Workflow creation and execution
    - SPARC methodology modes
    - Pipeline management
    - Parallel/batch execution
    - Automation rules and triggers
    """

    def __init__(self, timeout: Optional[float] = None, use_flow_nexus: bool = False):
        """
        Initialize workflow client.

        Args:
            timeout: Operation timeout in seconds
            use_flow_nexus: Use Flow-Nexus for enhanced workflows
        """
        self.config = get_config()
        self.timeout = timeout or self.config.get_timeout('workflow')
        self.use_flow_nexus = use_flow_nexus and self.config.is_server_enabled('flow-nexus')
        self.log_dir = self.config.get_log_dir()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / 'workflow_client.jsonl'

    def _log(self, operation: str, params: Dict, result: Any, success: bool, elapsed: float):
        """Log workflow operation."""
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
        if not self.config.is_feature_enabled('workflow'):
            return None

        use_timeout = timeout or self.timeout
        server = 'flow-nexus' if self.use_flow_nexus else 'claude-flow'

        start_time = time.time()
        try:
            if server == 'flow-nexus':
                cmd = ['npx', 'flow-nexus@latest', 'mcp', 'call', tool_name, json.dumps(params)]
            else:
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
    # WORKFLOW OPERATIONS
    # =========================================================================

    def create_workflow(self, name: str, steps: List[Dict],
                        triggers: Optional[List[str]] = None,
                        description: Optional[str] = None,
                        priority: int = 5) -> Optional[Dict]:
        """
        Create a custom workflow.

        Args:
            name: Workflow name
            steps: Workflow steps [{name, action, params, dependencies}]
            triggers: Event triggers
            description: Workflow description
            priority: Priority (0-10)

        Returns:
            Workflow creation result with workflow_id
        """
        params = {
            'name': name,
            'steps': steps,
            'priority': priority
        }
        if triggers:
            params['triggers'] = triggers
        if description:
            params['description'] = description
        return self._call_tool('workflow_create', params)

    def execute_workflow(self, workflow_id: str, params: Optional[Dict] = None,
                         async_exec: bool = False) -> Optional[Dict]:
        """
        Execute a workflow.

        Args:
            workflow_id: Workflow ID
            params: Execution parameters
            async_exec: Execute asynchronously via queue

        Returns:
            Execution result
        """
        exec_params = {'workflowId': workflow_id}
        if params:
            exec_params['params'] = params
        if async_exec:
            exec_params['async'] = True
        return self._call_tool('workflow_execute', exec_params)

    def workflow_status(self, workflow_id: Optional[str] = None,
                        execution_id: Optional[str] = None,
                        include_metrics: bool = False) -> Optional[Dict]:
        """
        Get workflow status.

        Args:
            workflow_id: Workflow ID
            execution_id: Specific execution ID
            include_metrics: Include performance metrics

        Returns:
            Workflow status
        """
        params = {'include_metrics': include_metrics}
        if workflow_id:
            params['workflow_id'] = workflow_id
        if execution_id:
            params['execution_id'] = execution_id
        return self._call_tool('workflow_status', params)

    def export_workflow(self, workflow_id: str, format: str = 'json') -> Optional[str]:
        """
        Export workflow definition.

        Args:
            workflow_id: Workflow ID
            format: Export format (json, yaml)

        Returns:
            Exported workflow definition
        """
        result = self._call_tool('workflow_export', {
            'workflowId': workflow_id,
            'format': format
        })
        return result.get('definition') if result else None

    def workflow_template(self, action: str, template: Optional[Dict] = None) -> Optional[Dict]:
        """
        Manage workflow templates.

        Args:
            action: Action (list, get, create, delete)
            template: Template definition for create

        Returns:
            Template operation result
        """
        params = {'action': action}
        if template:
            params['template'] = template
        return self._call_tool('workflow_template', params)

    def workflow_list(self, status: Optional[str] = None, limit: int = 10,
                      offset: int = 0) -> Optional[List]:
        """
        List workflows.

        Args:
            status: Filter by status
            limit: Maximum results
            offset: Skip results

        Returns:
            List of workflows
        """
        params = {'limit': limit, 'offset': offset}
        if status:
            params['status'] = status
        result = self._call_tool('workflow_list', params)
        return result.get('workflows', []) if result else None

    # =========================================================================
    # SPARC METHODOLOGY
    # =========================================================================

    def sparc_mode(self, mode: str, task_description: str,
                   options: Optional[Dict] = None) -> Optional[Dict]:
        """
        Run SPARC development mode.

        Args:
            mode: SPARC mode (dev, api, ui, test, refactor)
            task_description: Task to work on
            options: Additional options

        Returns:
            SPARC mode execution result
        """
        params = {
            'mode': mode,
            'task_description': task_description
        }
        if options:
            params['options'] = options
        return self._call_tool('sparc_mode', params)

    def sparc_specification(self, task: str) -> Optional[Dict]:
        """Run SPARC Specification phase."""
        return self.sparc_mode('spec', task)

    def sparc_pseudocode(self, task: str) -> Optional[Dict]:
        """Run SPARC Pseudocode phase."""
        return self.sparc_mode('pseudocode', task)

    def sparc_architecture(self, task: str) -> Optional[Dict]:
        """Run SPARC Architecture phase."""
        return self.sparc_mode('architecture', task)

    def sparc_refinement(self, task: str) -> Optional[Dict]:
        """Run SPARC Refinement phase (TDD)."""
        return self.sparc_mode('test', task)

    def sparc_completion(self, task: str) -> Optional[Dict]:
        """Run SPARC Completion phase."""
        return self.sparc_mode('dev', task)

    # =========================================================================
    # AUTOMATION
    # =========================================================================

    def automation_setup(self, rules: List[Dict]) -> Optional[Dict]:
        """
        Setup automation rules.

        Args:
            rules: Automation rules [{condition, action, priority}]

        Returns:
            Automation setup result
        """
        return self._call_tool('automation_setup', {'rules': rules})

    def pipeline_create(self, config: Dict) -> Optional[Dict]:
        """
        Create CI/CD pipeline.

        Args:
            config: Pipeline configuration

        Returns:
            Pipeline creation result
        """
        return self._call_tool('pipeline_create', {'config': config})

    def scheduler_manage(self, action: str, schedule: Optional[Dict] = None) -> Optional[Dict]:
        """
        Manage task scheduling.

        Args:
            action: Action (list, create, delete, pause, resume)
            schedule: Schedule definition for create

        Returns:
            Scheduler operation result
        """
        params = {'action': action}
        if schedule:
            params['schedule'] = schedule
        return self._call_tool('scheduler_manage', params)

    def trigger_setup(self, events: List[str], actions: List[Dict]) -> Optional[Dict]:
        """
        Setup event triggers.

        Args:
            events: Events to trigger on
            actions: Actions to execute

        Returns:
            Trigger setup result
        """
        return self._call_tool('trigger_setup', {
            'events': events,
            'actions': actions
        })

    # =========================================================================
    # EXECUTION
    # =========================================================================

    def batch_process(self, items: List[Any], operation: str) -> Optional[Dict]:
        """
        Batch processing.

        Args:
            items: Items to process
            operation: Operation to apply

        Returns:
            Batch processing result
        """
        return self._call_tool('batch_process', {
            'items': items,
            'operation': operation
        })

    def parallel_execute(self, tasks: List[Dict]) -> Optional[Dict]:
        """
        Execute tasks in parallel.

        Args:
            tasks: Tasks to execute [{name, action, params}]

        Returns:
            Parallel execution result
        """
        return self._call_tool('parallel_execute', {'tasks': tasks})

    # =========================================================================
    # FLOW-NEXUS ENHANCED (when enabled)
    # =========================================================================

    def workflow_agent_assign(self, task_id: str, agent_type: Optional[str] = None,
                              use_vector_similarity: bool = True) -> Optional[Dict]:
        """
        Assign optimal agent to task (Flow-Nexus).

        Args:
            task_id: Task ID
            agent_type: Preferred agent type
            use_vector_similarity: Use vector matching

        Returns:
            Agent assignment result
        """
        if not self.config.is_server_enabled('flow-nexus'):
            return None

        old_flow_nexus = self.use_flow_nexus
        self.use_flow_nexus = True

        params = {'task_id': task_id, 'use_vector_similarity': use_vector_similarity}
        if agent_type:
            params['agent_type'] = agent_type

        result = self._call_tool('workflow_agent_assign', params)
        self.use_flow_nexus = old_flow_nexus
        return result

    def workflow_queue_status(self, queue_name: Optional[str] = None,
                              include_messages: bool = False) -> Optional[Dict]:
        """
        Check message queue status (Flow-Nexus).

        Args:
            queue_name: Queue name
            include_messages: Include pending messages

        Returns:
            Queue status
        """
        if not self.config.is_server_enabled('flow-nexus'):
            return None

        old_flow_nexus = self.use_flow_nexus
        self.use_flow_nexus = True

        params = {'include_messages': include_messages}
        if queue_name:
            params['queue_name'] = queue_name

        result = self._call_tool('workflow_queue_status', params)
        self.use_flow_nexus = old_flow_nexus
        return result

    def workflow_audit_trail(self, workflow_id: Optional[str] = None,
                             limit: int = 50) -> Optional[List]:
        """
        Get workflow audit trail (Flow-Nexus).

        Args:
            workflow_id: Workflow ID
            limit: Maximum events

        Returns:
            Audit trail events
        """
        if not self.config.is_server_enabled('flow-nexus'):
            return None

        old_flow_nexus = self.use_flow_nexus
        self.use_flow_nexus = True

        params = {'limit': limit}
        if workflow_id:
            params['workflow_id'] = workflow_id

        result = self._call_tool('workflow_audit_trail', params)
        self.use_flow_nexus = old_flow_nexus
        return result.get('events', []) if result else None

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def is_available(self) -> bool:
        """Check if workflow services are available."""
        try:
            result = self.workflow_list(limit=1)
            return result is not None
        except Exception:
            return False


# Convenience function
def get_workflow_client(timeout: Optional[float] = None, use_flow_nexus: bool = False) -> WorkflowClient:
    """Get a workflow client instance."""
    return WorkflowClient(timeout=timeout, use_flow_nexus=use_flow_nexus)
