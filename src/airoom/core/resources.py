"""Packaged resource access for AIroom skills and templates."""

from pathlib import Path


class ResourceManager:
    """Manages access to packaged resources (skills, templates)."""

    def __init__(self) -> None:
        """Initialize the resource manager.
        
        Resources are located in the airoom package's resources directory.
        """
        # Resources are in the airoom package directory
        self._package_root = Path(__file__).parent.parent
        self._resources_root = self._package_root / "resources"

    def get_resource_path(self, relative_path: str) -> Path:
        """Get the path to a packaged resource.
        
        Args:
            relative_path: Path relative to the resources directory.
            
        Returns:
            Path to the resource (may not exist).
        """
        return self._resources_root / relative_path

    def read_resource(self, relative_path: str) -> str:
        """Read a packaged resource file.
        
        Args:
            relative_path: Path relative to the resources directory.
            
        Returns:
            Content of the resource file as string.
            
        Raises:
            FileNotFoundError: If the resource does not exist.
        """
        path = self.get_resource_path(relative_path)
        return path.read_text(encoding="utf-8")

    def list_packaged_skills(self) -> list[str]:
        """List all skill names packaged with AIroom.
        
        Returns:
            Sorted list of skill directory names.
        """
        skills_dir = self.get_resource_path("skills")
        if not skills_dir.exists():
            return []
        return sorted([d.name for d in skills_dir.iterdir() if d.is_dir()])

    def list_packaged_templates(self) -> list[str]:
        """List all template names packaged with AIroom.
        
        Returns:
            Sorted list of template file names.
        """
        templates_dir = self.get_resource_path("templates")
        if not templates_dir.exists():
            return []
        return sorted([f.name for f in templates_dir.iterdir() if f.is_file()])