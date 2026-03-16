"""
Neural network client for training, inference, and pattern recognition.
Supports both Claude-Flow and Flow-Nexus neural tools.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import time

try:
    from .config_loader import get_config
except ImportError:
    from config_loader import get_config


class NeuralClient:
    """
    Client for neural network operations via MCP tools.

    Supports:
    - Pattern training and recognition
    - Model inference and prediction
    - Cognitive behavior analysis
    - Distributed neural clusters (Flow-Nexus)
    """

    def __init__(self, timeout: Optional[float] = None, use_flow_nexus: bool = False):
        """
        Initialize neural client.

        Args:
            timeout: Operation timeout in seconds
            use_flow_nexus: Use Flow-Nexus for distributed training
        """
        self.config = get_config()
        self.timeout = timeout or self.config.get_timeout('neural')
        self.use_flow_nexus = use_flow_nexus and self.config.is_server_enabled('flow-nexus')
        self.log_dir = self.config.get_log_dir()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / 'neural_client.jsonl'

    def _log(self, operation: str, params: Dict, result: Any, success: bool, elapsed: float):
        """Log neural operation."""
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
        if not self.config.is_feature_enabled('neural'):
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
    # TRAINING OPERATIONS
    # =========================================================================

    def train_pattern(self, pattern_type: str, training_data: Union[str, Dict, List],
                      epochs: int = 50) -> Optional[Dict]:
        """
        Train neural patterns with WASM SIMD acceleration.

        Args:
            pattern_type: Pattern type (coordination, optimization, prediction)
            training_data: Training data (string, dict, or list)
            epochs: Number of training epochs

        Returns:
            Training result with metrics
        """
        data_str = json.dumps(training_data) if not isinstance(training_data, str) else training_data
        return self._call_tool('neural_train', {
            'pattern_type': pattern_type,
            'training_data': data_str,
            'epochs': epochs
        })

    def train_distributed(self, cluster_id: str, dataset: str, epochs: int = 10,
                          batch_size: int = 32, learning_rate: float = 0.001,
                          optimizer: str = 'adam', federated: bool = False) -> Optional[Dict]:
        """
        Train across distributed neural cluster (Flow-Nexus only).

        Args:
            cluster_id: Neural cluster ID
            dataset: Training dataset identifier
            epochs: Training epochs
            batch_size: Batch size
            learning_rate: Learning rate
            optimizer: Optimizer (adam, sgd, rmsprop, adagrad)
            federated: Enable federated learning

        Returns:
            Distributed training result
        """
        if not self.config.is_server_enabled('flow-nexus'):
            return None

        old_flow_nexus = self.use_flow_nexus
        self.use_flow_nexus = True

        result = self._call_tool('neural_train_distributed', {
            'cluster_id': cluster_id,
            'dataset': dataset,
            'epochs': epochs,
            'batch_size': batch_size,
            'learning_rate': learning_rate,
            'optimizer': optimizer,
            'federated': federated
        })

        self.use_flow_nexus = old_flow_nexus
        return result

    # =========================================================================
    # INFERENCE OPERATIONS
    # =========================================================================

    def predict(self, model_id: str, input_data: Union[str, Dict, List]) -> Optional[Dict]:
        """
        Run prediction on a trained model.

        Args:
            model_id: Model identifier
            input_data: Input data for prediction

        Returns:
            Prediction result
        """
        data_str = json.dumps(input_data) if not isinstance(input_data, str) else input_data
        return self._call_tool('neural_predict', {
            'modelId': model_id,
            'input': data_str
        })

    def inference_run(self, model_id: str, data: List) -> Optional[Dict]:
        """
        Run inference on a batch of data.

        Args:
            model_id: Model identifier
            data: Batch data array

        Returns:
            Inference results
        """
        return self._call_tool('inference_run', {
            'modelId': model_id,
            'data': data
        })

    def predict_distributed(self, cluster_id: str, input_data: Union[str, Dict, List],
                            aggregation: str = 'mean') -> Optional[Dict]:
        """
        Run prediction across distributed cluster (Flow-Nexus only).

        Args:
            cluster_id: Neural cluster ID
            input_data: Input data
            aggregation: Aggregation method (mean, majority, weighted, ensemble)

        Returns:
            Distributed prediction result
        """
        if not self.config.is_server_enabled('flow-nexus'):
            return None

        data_str = json.dumps(input_data) if not isinstance(input_data, str) else input_data
        old_flow_nexus = self.use_flow_nexus
        self.use_flow_nexus = True

        result = self._call_tool('neural_predict_distributed', {
            'cluster_id': cluster_id,
            'input_data': data_str,
            'aggregation': aggregation
        })

        self.use_flow_nexus = old_flow_nexus
        return result

    # =========================================================================
    # PATTERN RECOGNITION
    # =========================================================================

    def recognize_patterns(self, data: List, patterns: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Recognize patterns in data.

        Args:
            data: Data to analyze
            patterns: Optional pattern types to look for

        Returns:
            Pattern recognition results
        """
        params = {'data': data}
        if patterns:
            params['patterns'] = patterns
        return self._call_tool('pattern_recognize', params)

    def analyze_patterns(self, action: str = 'analyze', operation: Optional[str] = None,
                         outcome: Optional[str] = None, metadata: Optional[Dict] = None) -> Optional[Dict]:
        """
        Analyze cognitive patterns.

        Args:
            action: Action type (analyze, learn, predict)
            operation: Operation being analyzed
            outcome: Outcome of operation
            metadata: Additional metadata

        Returns:
            Pattern analysis result
        """
        params = {'action': action}
        if operation:
            params['operation'] = operation
        if outcome:
            params['outcome'] = outcome
        if metadata:
            params['metadata'] = metadata
        return self._call_tool('neural_patterns', params)

    def cognitive_analyze(self, behavior: str) -> Optional[Dict]:
        """
        Analyze cognitive behavior patterns.

        Args:
            behavior: Behavior description to analyze

        Returns:
            Cognitive analysis result
        """
        return self._call_tool('cognitive_analyze', {'behavior': behavior})

    def learning_adapt(self, experience: Dict) -> Optional[Dict]:
        """
        Trigger adaptive learning from experience.

        Args:
            experience: Experience data

        Returns:
            Adaptation result
        """
        return self._call_tool('learning_adapt', {'experience': experience})

    # =========================================================================
    # MODEL MANAGEMENT
    # =========================================================================

    def neural_status(self, model_id: Optional[str] = None) -> Optional[Dict]:
        """Get neural network status."""
        params = {}
        if model_id:
            params['modelId'] = model_id
        return self._call_tool('neural_status', params)

    def load_model(self, model_path: str) -> Optional[Dict]:
        """
        Load a pre-trained model.

        Args:
            model_path: Path to model file

        Returns:
            Load result with model_id
        """
        return self._call_tool('model_load', {'modelPath': model_path})

    def save_model(self, model_id: str, path: str) -> bool:
        """
        Save a trained model.

        Args:
            model_id: Model identifier
            path: Save path

        Returns:
            True if saved successfully
        """
        result = self._call_tool('model_save', {
            'modelId': model_id,
            'path': path
        })
        return result is not None

    def compress_model(self, model_id: str, ratio: float = 0.5) -> Optional[Dict]:
        """
        Compress a neural model.

        Args:
            model_id: Model identifier
            ratio: Compression ratio (0-1)

        Returns:
            Compression result
        """
        return self._call_tool('neural_compress', {
            'modelId': model_id,
            'ratio': ratio
        })

    def create_ensemble(self, models: List[str], strategy: str = 'voting') -> Optional[Dict]:
        """
        Create model ensemble.

        Args:
            models: List of model IDs
            strategy: Ensemble strategy

        Returns:
            Ensemble creation result
        """
        return self._call_tool('ensemble_create', {
            'models': models,
            'strategy': strategy
        })

    def transfer_learn(self, source_model: str, target_domain: str) -> Optional[Dict]:
        """
        Apply transfer learning.

        Args:
            source_model: Source model ID
            target_domain: Target domain

        Returns:
            Transfer learning result
        """
        return self._call_tool('transfer_learn', {
            'sourceModel': source_model,
            'targetDomain': target_domain
        })

    # =========================================================================
    # EXPLAINABILITY
    # =========================================================================

    def explain_prediction(self, model_id: str, prediction: Dict) -> Optional[Dict]:
        """
        Explain a model prediction.

        Args:
            model_id: Model identifier
            prediction: Prediction to explain

        Returns:
            Explanation result
        """
        return self._call_tool('neural_explain', {
            'modelId': model_id,
            'prediction': prediction
        })

    # =========================================================================
    # OPTIMIZATION
    # =========================================================================

    def wasm_optimize(self, operation: Optional[str] = None) -> Optional[Dict]:
        """
        Apply WASM SIMD optimization.

        Args:
            operation: Optional specific operation to optimize

        Returns:
            Optimization result
        """
        params = {}
        if operation:
            params['operation'] = operation
        return self._call_tool('wasm_optimize', params)

    # =========================================================================
    # CLUSTER MANAGEMENT (Flow-Nexus)
    # =========================================================================

    def cluster_init(self, name: str, architecture: str = 'transformer',
                     topology: str = 'mesh', consensus: str = 'proof-of-learning',
                     daa_enabled: bool = True) -> Optional[Dict]:
        """
        Initialize distributed neural cluster (Flow-Nexus only).

        Args:
            name: Cluster name
            architecture: Neural architecture (transformer, cnn, rnn, gnn, hybrid)
            topology: Network topology (mesh, ring, star, hierarchical)
            consensus: DAA consensus mechanism
            daa_enabled: Enable DAA coordination

        Returns:
            Cluster initialization result
        """
        if not self.config.is_server_enabled('flow-nexus'):
            return None

        old_flow_nexus = self.use_flow_nexus
        self.use_flow_nexus = True

        result = self._call_tool('neural_cluster_init', {
            'name': name,
            'architecture': architecture,
            'topology': topology,
            'consensus': consensus,
            'daaEnabled': daa_enabled
        })

        self.use_flow_nexus = old_flow_nexus
        return result

    def cluster_status(self, cluster_id: str) -> Optional[Dict]:
        """Get neural cluster status (Flow-Nexus only)."""
        if not self.config.is_server_enabled('flow-nexus'):
            return None

        old_flow_nexus = self.use_flow_nexus
        self.use_flow_nexus = True
        result = self._call_tool('neural_cluster_status', {'cluster_id': cluster_id})
        self.use_flow_nexus = old_flow_nexus
        return result

    def cluster_terminate(self, cluster_id: str) -> bool:
        """Terminate neural cluster (Flow-Nexus only)."""
        if not self.config.is_server_enabled('flow-nexus'):
            return False

        old_flow_nexus = self.use_flow_nexus
        self.use_flow_nexus = True
        result = self._call_tool('neural_cluster_terminate', {'cluster_id': cluster_id})
        self.use_flow_nexus = old_flow_nexus
        return result is not None

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def is_available(self) -> bool:
        """Check if neural services are available."""
        try:
            result = self.neural_status()
            return result is not None
        except Exception:
            return False


# Convenience function
def get_neural_client(timeout: Optional[float] = None, use_flow_nexus: bool = False) -> NeuralClient:
    """Get a neural client instance."""
    return NeuralClient(timeout=timeout, use_flow_nexus=use_flow_nexus)
