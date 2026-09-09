"""GCN inference adapter for the legacy graph model."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import Settings
from ..exceptions import ArtifactMissingError, PredictionError
from ..schemas import AOPRelation


def confidence_to_woe(confidence: int) -> str:
    """Map a numeric edge confidence to a weight-of-evidence label.

    Args:
        confidence: Configured confidence value; must be 1, 3, or 5.

    Returns:
        Corresponding ``low``, ``moderate``, or ``high`` label.

    Raises:
        ValueError: Raised when the confidence value is unsupported.
    """
    mapping = {5: "high", 3: "moderate", 1: "low"}
    try:
        return mapping[confidence]
    except KeyError as exc:
        raise ValueError(f"Unsupported confidence: {confidence}") from exc


class GCNPredictor:
    """Loads the GCN once and repeatedly evaluates different event activations."""

    def __init__(self, settings: Settings, model_path: Path) -> None:
        """Load the graph model and move it to an available device.

        Args:
            settings: Validated graph and event settings.
            model_path: Path to the serialized PyTorch state dict.

        Raises:
            ArtifactMissingError: Raised when the state dict does not exist.
            PredictionError: Raised when PyTorch or the model cannot initialize.
        """
        if not model_path.is_file():
            raise ArtifactMissingError(f"GCN model not found: {model_path}")
        self.settings = settings
        self.model_path = model_path
        try:
            import torch

            self._torch = torch
            self._device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
            self._model = _build_model(torch).to(self._device)
            state = torch.load(
                model_path,
                map_location=self._device,
                weights_only=True,
            )
            self._model.load_state_dict(state)
            self._model.eval()
        except Exception as exc:
            raise PredictionError(f"Failed to load GCN model: {exc}") from exc

    def predict(self, endpoint_results: dict[str, int]) -> tuple[int, tuple[AOPRelation, ...]]:
        """Predict graph-level EDC activity from endpoint activations.

        Args:
            endpoint_results: Qualitative activity results keyed by event ID.

        Returns:
            Graph classification result plus serializable AOP relation values.

        Raises:
            PredictionError: Raised when graph tensor construction or model
                inference fails.
        """
        torch = self._torch
        try:
            ordered = [
                int(endpoint_results[self.settings.index_to_event[index]])
                for index in sorted(self.settings.index_to_event)
            ]
            node_indexes = list(range(len(ordered)))
            x = torch.tensor(
                list(zip(node_indexes, ordered, strict=True)),
                dtype=torch.float,
                device=self._device,
            )
            sources = [source for source, _ in self.settings.edges]
            targets = [target for _, target in self.settings.edges]
            edge_index = torch.tensor([sources, targets], dtype=torch.long, device=self._device)
            edge_values: list[float] = []
            relations: list[AOPRelation] = []
            for (source, target), confidence in zip(
                self.settings.edges, self.settings.edge_confidences, strict=True
            ):
                source_value, target_value = ordered[source], ordered[target]
                value: float | int = 1 if source_value == target_value == 1 else 0
                if source_value != target_value:
                    value = 0.5
                edge_values.append(value)
                relations.append(
                    AOPRelation(
                        source=self.settings.index_to_event[source],
                        target=self.settings.index_to_event[target],
                        value=value,
                        weight_of_evidence=confidence_to_woe(confidence),
                    )
                )
            for index, woe in zip(
                self.settings.single_event_indexes,
                self.settings.single_event_woe,
                strict=True,
            ):
                event_id = self.settings.index_to_event[index]
                relations.append(
                    AOPRelation(
                        source="EDCs",
                        target=event_id,
                        value=ordered[index],
                        weight_of_evidence=woe,
                    )
                )
            edge_attr = torch.tensor(
                list(zip(edge_values, self.settings.edge_confidences, strict=True)),
                dtype=torch.float,
                device=self._device,
            )
            batch = torch.zeros(len(ordered), dtype=torch.long, device=self._device)
            with torch.inference_mode():
                output = self._model(
                    x=x,
                    edge_index=edge_index,
                    batch=batch,
                    edge_attr=edge_attr,
                )
            prediction = int(output.argmax(dim=1).detach().cpu().item())
            return prediction, tuple(relations)
        except PredictionError:
            raise
        except Exception as exc:
            raise PredictionError(f"GCN prediction failed: {exc}") from exc


def _build_model(torch: Any) -> Any:
    """Build the graph network architecture exactly matching the legacy weights.

    Args:
        torch: Imported PyTorch module.

    Returns:
        GCN module instance compatible with the legacy weights.
    """
    import torch.nn.functional as functional
    from torch.nn import Linear, Parameter
    from torch_geometric.nn import MessagePassing, global_mean_pool
    from torch_geometric.utils import add_self_loops, degree

    class GCNConvEdge(MessagePassing):
        """Message-passing layer combining node and edge embeddings."""

        def __init__(self, in_channels: int, out_channels: int, edge_channels: int):
            """Initialize node, edge, and bias parameters.

            Args:
                in_channels: Number of input node features.
                out_channels: Number of output embedding features.
                edge_channels: Number of input edge features.
            """
            super().__init__(aggr="add")
            # Attribute names are part of the serialized legacy state-dict contract.
            self.lin = Linear(in_channels, out_channels, bias=False)
            self.bias = Parameter(torch.empty(2 * out_channels))
            self.lin_edge = Linear(edge_channels, out_channels, bias=False)
            self.reset_parameters()

        def reset_parameters(self) -> None:
            """Reset trainable parameters using the default PyTorch strategy."""
            self.lin.reset_parameters()
            self.bias.data.zero_()
            self.lin_edge.reset_parameters()

        def forward(self, x: Any, edge_index: Any, edge_features: Any) -> tuple[Any, Any]:
            """Run one normalized message-passing step.

            Args:
                x: Node feature tensor.
                edge_index: Directed edge index tensor.
                edge_features: Edge feature tensor.

            Returns:
                Updated node and edge embeddings.
            """
            edge_index, _ = add_self_loops(edge_index, num_nodes=x.size(0))
            x = self.lin(x)
            edge_features = self.lin_edge(edge_features)
            extended = torch.cat(
                [
                    edge_features,
                    torch.zeros(
                        [x.shape[0], edge_features.shape[1]],
                        device=edge_features.device,
                        dtype=edge_features.dtype,
                    ),
                ],
                dim=0,
            )
            row, column = edge_index
            node_degree = degree(column, x.size(0), dtype=x.dtype)
            inverse_sqrt = node_degree.pow(-0.5)
            inverse_sqrt[inverse_sqrt == float("inf")] = 0
            normalization = inverse_sqrt[row] * inverse_sqrt[column]
            output = self.propagate(edge_index, x=x, norm=normalization, ex=extended)
            return output + self.bias, edge_features

        def message(self, x_j: Any, norm: Any, ex: Any) -> Any:
            """Produce normalized messages for neighboring nodes.

            Args:
                x_j: Source-node embeddings selected by PyG.
                norm: Per-edge normalization coefficient.
                ex: Edge embeddings aligned with each message.

            Returns:
                Concatenated and normalized message tensor.
            """
            return norm.view(-1, 1) * torch.cat([x_j, ex], dim=1)

    class GCN(torch.nn.Module):
        """Three-layer graph classifier matching the legacy state dict."""

        def __init__(self) -> None:
            """Initialize graph convolution and classification layers."""
            super().__init__()
            torch.manual_seed(12345)
            self.conv1 = GCNConvEdge(2, 50, 2)
            self.conv2 = GCNConvEdge(100, 20, 50)
            self.conv3 = GCNConvEdge(40, 60, 20)
            self.lin = Linear(120, 2)

        def forward(self, x: Any, edge_index: Any, batch: Any, edge_attr: Any) -> Any:
            """Compute graph classification logits.

            Args:
                x: Node feature tensor.
                edge_index: Directed edge index tensor.
                batch: Graph index each node belongs to.
                edge_attr: Edge feature tensor.

            Returns:
                Binary graph-classification logits.
            """
            x, edge_features = self.conv1(x, edge_index, edge_attr)
            x = x.relu()
            x, edge_features = self.conv2(x, edge_index, edge_features)
            x = x.relu()
            x, _ = self.conv3(x, edge_index, edge_features)
            x = global_mean_pool(x, batch)
            x = functional.dropout(x, p=0.5, training=self.training)
            return self.lin(x)

    return GCN()
