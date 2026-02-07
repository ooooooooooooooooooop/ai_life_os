"""
CLI 命令：lifeos anchor
仪式性更新入口
"""
import click
import sys
from pathlib import Path
from typing import Optional

# 添加项目根目录到 sys.path，以便导入 core 模块
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from core.blueprint_anchor import AnchorManager, BlueprintAnchor, AnchorDiff

BLUEPRINT_PATH = project_root / "docs" / "concepts" / "better_human_blueprint.md"


@click.group()
def anchor():
    """Blueprint Anchor 管理命令"""
    pass


@anchor.command()
def update():
    """生成新的 Anchor 草稿"""
    manager = AnchorManager()
    
    click.echo(f"📄 读取 Blueprint: {BLUEPRINT_PATH.name}")
    if not BLUEPRINT_PATH.exists():
        click.echo("❌ 错误: Blueprint 文件不存在", err=True)
        return

    click.echo("📝 正在分析 Blueprint (ANCHOR_EXTRACTION Mode)...")
    try:
        draft = manager.generate_draft(str(BLUEPRINT_PATH))
    except Exception as e:
        click.echo(f"❌ 分析失败: {e}", err=True)
        return
    
    click.echo(f"\n✅ 生成草稿版本: {draft.version}")
    click.echo(f"📅 创建时间: {draft.created_at}")
    click.echo(f"\n🔒 不可谈判底线 ({len(draft.non_negotiables)} 项):")
    for item in draft.non_negotiables:
        click.echo(f"  - {item}")
    
    click.echo(f"\n🎯 长期承诺 ({len(draft.long_horizon_commitments)} 项):")
    for item in draft.long_horizon_commitments:
        click.echo(f"  - {item}")
    
    click.echo(f"\n❌ 反价值 ({len(draft.anti_values)} 项):")
    for item in draft.anti_values:
        click.echo(f"  - {item}")
    
    click.echo(f"\n⚠️ 本能劫持模式 ({len(draft.instinct_adversaries)} 项):")
    for item in draft.instinct_adversaries:
        click.echo(f"  - {item}")
    
    click.echo("\n💡 使用 'lifeos anchor activate' 确认激活")


@anchor.command()
def diff():
    """显示当前 Anchor 与新草稿的差异"""
    manager = AnchorManager()
    
    if not BLUEPRINT_PATH.exists():
        click.echo("❌ 错误: Blueprint 文件不存在", err=True)
        return

    current = manager.get_current()
    if not current:
        click.echo("ℹ️ 当前没有激活的 Anchor")
    else:
        click.echo(f"ℹ️ 当前版本: {current.version} ({current.created_at})")

    click.echo("📝 分析新 Blueprint...")
    try:
        draft = manager.generate_draft(str(BLUEPRINT_PATH))
    except Exception as e:
        click.echo(f"❌ 分析失败: {e}", err=True)
        return
    
    diff_result = manager.diff(current, draft)
    
    if diff_result.status == "new":
        click.echo("\n🆕 这是第一个 Anchor (Version 1)")
        click.echo(f"  + {len(draft.non_negotiables)} 个不可谈判底线")
        click.echo(f"  + {len(draft.long_horizon_commitments)} 个长期承诺")
        click.echo(f"  + {len(draft.anti_values)} 个反价值")
        click.echo(f"  + {len(draft.instinct_adversaries)} 个本能劫持模式")
    
    elif diff_result.status == "unchanged":
        click.echo("\n✅ 没有变更。当前 Anchor 与 Blueprint 一致。")
        
    else:
        click.echo(f"\n📊 版本变更: {diff_result.version_change}")
        
        _print_set_diff("不可谈判底线", diff_result.added_non_negotiables, diff_result.removed_non_negotiables)
        _print_set_diff("长期承诺", diff_result.added_commitments, diff_result.removed_commitments)
        _print_set_diff("反价值", diff_result.added_anti_values, diff_result.removed_anti_values)
        _print_set_diff("本能劫持模式", diff_result.added_adversaries, diff_result.removed_adversaries)


def _print_set_diff(title: str, added: Optional[set], removed: Optional[set]):
    if not added and not removed:
        return
    
    click.echo(f"\n[{title}]")
    if added:
        for item in added:
            click.echo(f"  + {item}")
    if removed:
        for item in removed:
            click.echo(f"  - {item}")


@anchor.command()
@click.confirmation_option(prompt="⚠️ 确认你现在处于清醒、理性的状态 (Blueprint Self)？")
def activate():
    """确认激活新 Anchor（仪式性操作）"""
    manager = AnchorManager()
    
    if not BLUEPRINT_PATH.exists():
        click.echo("❌ 错误: Blueprint 文件不存在", err=True)
        return

    click.echo("📝 生成最终 Anchor...")
    try:
        draft = manager.generate_draft(str(BLUEPRINT_PATH))
    except Exception as e:
        click.echo(f"❌ 生成失败: {e}", err=True)
        return

    # 再次检查是否有变更（如果只是为了更新 hash/时间戳，也可以激活）
    current = manager.get_current()
    diff_result = manager.diff(current, draft)
    
    if current and diff_result.status == "unchanged":
        if not click.confirm("内容无变更，是否强制更新版本号？"):
            click.echo("操作取消")
            return

    try:
        confirmed = manager.activate(draft)
        click.echo(f"\n✅ Anchor {confirmed.version} 已激活")
        click.echo(f"📁 存储位置: data/anchors/current.json")
        click.echo("🛡️ Guardian 将基于此版本进行护卫")
    except Exception as e:
         click.echo(f"❌ 激活失败: {e}", err=True)


if __name__ == "__main__":
    anchor()
