# G4UniversalSim J1 前端 · 单个体积着色方案（PySide6 + PyVista）

## 一、架构定位（先说清楚边界）

- **视图偏好层**（ViewOverrides）：`{key|material: {"color": "#RRGGBB", "opacity": float, "scope": "key|material"}}`，**不写进项目文件、不进 F5 回放、不触碰后端 `vis.*`**。
- **自动状态层**（现有 `style(item)`）：选中/世界/径迹 opacity 全由 `style()` 给出，是"基线"。
- **合并规则**：`final = override(user) ?? auto(style)`，**用户值永远优先**；主题、选中、径迹变化只改 `auto`，不改 `override`。
- **几何刷新**：`prune(valid_keys, valid_materials)` 只保留仍存在项；被 prune 掉的 key/material 视为用户偏好失效（不做持久化假象）。

## 二、UI 目标

```
[作用域: (•) 单个 key  ( ) 材料]   [目标: ▾ combo]
[颜色: ■ #RRGGBB]  [选择...]     [不透明度: 85%]  [滑块]
[复位当前]  [复位全部]                      [3D 不可用：仅文本]
```

无 PyVista 时：整个"颜色/不透明度/复位"面板 `setDisabled(True)` + 提示"当前无 3D 视图，偏好不可调"。

## 三、核心实现片段

### 1. 偏好存储与合并（独立于 ViewState / 项目）

```python
# view/overrides.py
from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple

@dataclass
class Override:
    color:   Optional[str]   = None   # "#rrggbb" 规范化小写
    opacity: Optional[float] = None   # 0..1

class ViewOverrides:
    """仅视图偏好；不由项目/回放/后端 vis.* 持有。"""
    def __init__(self):
        self._by_key:      Dict[str, Override] = {}
        self._by_material: Dict[str, Override] = {}
        # 订阅者（PyVista widget）→ 只发"合并后姿态"，不发原始 override
        self._listeners = []

    def set(self, scope: str, target: str, *, color: str|None = None, opacity: float|None = None):
        book = self._by_key if scope == "key" else self._by_material
        ov = book.setdefault(target, Override())
        if color is not None:
            ov.color = color.lower()
        if opacity is not None:
            ov.opacity = max(0.0, min(1.0, float(opacity)))
        self._notify()

    def reset(self, scope: str|None = None, target: str|None = None):
        if scope is None:
            self._by_key.clear(); self._by_material.clear()
        else:
            book = self._by_key if scope == "key" else self._by_material
            if target is None: book.clear()
            else: book.pop(target, None)
        self._notify()

    def resolve(self, key: str, material: str, auto_color, auto_opacity) -> Tuple[str, float]:
        """用户优先于自动；key > material > auto。"""
        for book, tgt in ((self._by_key, key), (self._by_material, material)):
            ov = book.get(tgt)
            if ov:
                return (ov.color or auto_color,
                        ov.opacity if ov.opacity is not None else auto_opacity)
        return auto_color, auto_opacity

    # prune：几何刷新后调用，只保留仍有效项
    def prune(self, valid_keys: set[str], valid_materials: set[str]):
        for k in list(self._by_key):
            if k not in valid_keys: del self._by_key[k]
        for m in list(self._by_material):
            if m not in valid_materials: del self._by_material[m]
        self._notify()

    def subscribe(self, fn): self._listeners.append(fn)
    def _notify(self):
        for fn in self._listeners: fn()
```

### 2. 与 `style()` 的合并（在 PyVista widget 侧）

```python
# view/pv_widget.py
def _apply_style(self, item):
    # 1) 现有 style() 产出"自动值"（选中/世界/径迹），color 若 style 未给则由材质基线给
    base = self.viewstate.style(item)          # 例如 {"color":..., "opacity":...}
    auto_color   = base.get("color")   or self._material_color(item.material)
    auto_opacity = base.get("opacity", 1.0)

    # 2) 用户覆盖优先
    color, opacity = self.overrides.resolve(
        item.key, item.material, auto_color, auto_opacity)

    # 3) 落到 VTK actor（唯一写点）
    actor = self._actors[item.key]
    actor.GetProperty().SetColor(*hex_to_rgb01(color))
    actor.GetProperty().SetOpacity(float(opacity))
    actor.GetProperty().SetEdgeVisibility(False)  # 不在覆盖层改边线，避免"冲掉用户值"错觉

def _on_overrides_changed(self):
    for item in self.viewstate.items:  # key touchable path/name/material/world
        self._apply_style(item)
    self.render()
```

关键点：`overrides.resolve` 只发生在**写入点**，`style()` 本身无需改动；主题/选中/径迹变化也走 `_apply_style`，所以自动值可随时更新而用户值恒定不冲掉。

### 3. 主题（B/K/C 板 + light/dark/system 独立记忆）

```python
# view/theme.py
PALETTES = {
    "light": {                              # 浅色可选两套板
        "B": dict(bg="#0e7c86", fg="#ffffff"),   # 晶格
        "K": dict(bg="#1971c2", fg="#ffffff"),   # 软件
    },
    "dark": {
        "C": dict(bg="#111820", panel="#172029", fg="#8cc8f0"),  # 夜读
    },
}

def apply_theme(app, mode="system", *, light_palette="B"):
    """mode 与 light_palette 分级记忆；system 仅决定当前分支，不改 light 选择。"""
    resolved = mode
    if mode == "system":
        resolved = "dark" if _system_is_dark() else "light"
    if resolved == "light":
        p = PALETTES["light"][light_palette]    # light_palette 持久化在 QSettings
    else:
        p = PALETTES["dark"]["C"]
    _apply_palette(app, p)
    QSettings().setValue("theme/mode", mode)
    QSettings().setValue("theme/light_palette", light_palette)
```

陷阱对照：
- **system 分支不准覆盖 light 选择** → `light_palette` 独立键存储，切 system/切 dark 均不改它。
- **主题不算用户 override** → 主题只调 `_material_color`/基线，不影响 `ViewOverrides`。

### 4. UI 面板（下拉 / 颜色框 / 百分比 / 复位）

```python
# view/prefs_panel.py
class PrefsPanel(QWidget):
    def __init__(self, overrides: ViewOverrides, has_3d: bool):
        super().__init__()
        # 作用域、目标下拉、颜色按钮、不透明度滑块、复位按钮
        ...
        self.set_3d_available(has_3d)

    def set_3d_available(self, ok: bool):
        self.setEnabled(ok)
        self.hint.setText("" if ok else "无 3D 视图：颜色/不透明度不可调整")

    def _on_color(self):
        hexed = QColorDialog.getColor(
            QColor(self.color_btn.text()), self, options=QColorDialog.DontUseNativeDialog)
        if not hexed.isValid(): return
        self.overrides.set(self.scope, self.target,
                           color=hexed.name(QColor.HexRgb))
        self.color_btn.setText(hexed.name(QColor.HexRgb).lower())

    def _on_opacity(self, pct: int):
        self.overrides.set(self.scope, self.target, opacity=pct / 100.0)

    def _on_reset_current(self):
        self.overrides.reset(self.scope, self.target)

    def _on_reset_all(self):
        self.overrides.reset()
```

## 四、审视到的陷阱 & 对应规避

| 陷阱 | 规避 |
|---|---|
| 主题切换顺手清空用户 override | `apply_theme` 只调基线；`_notify` 走 `_apply_style`，不去动 `ViewOverrides` |
| 选中/径迹逻辑写回 override | 只写 `_apply_style` 的 auto 分支，override 无写入路径 |
| `system` 模式改 light_palette | light_palette 单独键，不进 system 分支状态 |
| 几何刷新后残留孤儿 key/material | `prune(valid_keys, valid_materials)` 显式清理；UI 目标下拉同步 `valid_*` |
| 覆盖层顺带改 edge/visibility 导致"复位不还原" | 覆盖层只写 `SetColor/SetOpacity`；其他属性留在 `style()` 语义内 |
| 无 PyVista 仍允许改 | `set_3d_available(False)` 整面板禁用 + 明确文案；**不做隐藏式本地缓存**，避免"看得到改不到" |
| F5 / 项目写入 | `ViewOverrides` 不由 `ProjectModel` 持有，序列化接口不暴露；回放不改它 |
| 后端 `vis.*` 污染 | `_apply_style` 只碰 actor Property，不写 `vis.*` 字段 |
| 混合 key + material 冲突 | 声明优先级：`key > material > style > material_color`，在 `resolve` 单一实现，UI 提示 |

## 五、装配顺序建议

1. 启动：`ViewOverrides()` → `PrefsPanel` → `PVWidget`；widget 订阅 `overrides.subscribe(self._on_overrides_changed)`。
2. 几何刷新：`widget.rebuild(valid_keys, valid_materials)` 内先 `overrides.prune(...)`，再逐 item `_apply_style`。
3. 主题菜单：`apply_theme(app, mode, light_palette=QSettings().value(...))`，只调 `_material_color` 基线，不触 override。
4. fallback：`has_3d=False` 时仍保留 `ViewOverrides` 对象与 prune 逻辑（保证刷新语义一致），但面板禁用文案明确"不可调整"。

按上述即可满足"用户值不倒、自动态可自由变、主题独立、刷新不腐、无 3D 不误导"的约束。未做视觉验收；不引入新事务控制器；`vis.*` 与项目/F5 均未触碰。
