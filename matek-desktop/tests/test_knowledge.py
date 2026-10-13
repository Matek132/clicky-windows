from companion.config import Settings
from companion.knowledge import search_references


def test_verified_recipe_reference_is_selected():
    selected = search_references("How do I make a lantern in Minecraft?", Settings())
    assert selected
    assert "eight iron nuggets" in selected[0][1]
    assert not search_references("How do I craft a torch in Minecraft?", Settings())
    assert not search_references("How do I craft a lantern in Terraria?", Settings())
    assert not search_references("How do I make a lantern?", Settings(knowledge_enabled=False))


def test_reference_file_bounds(tmp_path):
    (tmp_path / "large.md").write_text("# Large\n" + "x" * 40000)
    (tmp_path / "coral.md").write_text("# Coral\nCoral is the reference topic.")
    cfg = Settings(knowledge_folder=str(tmp_path))
    assert not search_references("large", cfg)
    assert search_references("explain coral", cfg)
