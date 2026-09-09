"""Project-specific exception hierarchy."""


class EdkgDlError(Exception):
    """Base exception for all anticipated application errors."""


class ConfigurationError(EdkgDlError):
    """Raised when configuration is missing or internally inconsistent."""


class ArtifactMissingError(ConfigurationError):
    """Raised when a required external model asset is unavailable."""


class ArtifactIntegrityError(ConfigurationError):
    """Raised when an external model asset fails digest verification."""


class AssetDownloadError(EdkgDlError):
    """Raised when model assets or the Java runtime cannot be downloaded."""


class InvalidSmilesError(EdkgDlError, ValueError):
    """Raised when a SMILES value is empty or has the wrong type."""


class FeatureExtractionError(EdkgDlError):
    """Raised when PaDEL cannot produce a usable feature row."""


class PredictionError(EdkgDlError):
    """Raised when a model cannot evaluate extracted features."""


class OutputExistsError(EdkgDlError, FileExistsError):
    """Raised when a report already exists and overwrite was not requested."""
