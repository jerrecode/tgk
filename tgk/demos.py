"""TGK interaction and layout laboratory; run: python -m tgk.demos --list.

Every scenario uses supported native widgets and can be built offline without
Android. Actual layout/gesture behavior should be checked with Termux:GUI.
"""
from __future__ import annotations
import argparse

from .theme import PRESETS, get_theme, resolve_theme, normalize_color, rgba_channels
from .widgets import (
    App, BoxLayout, GridLayout, ScrollView, Label, Button,
    TextInput, CheckBox, Switch, Slider, ProgressBar, ToggleButton,
)

SCENARIOS = {
    "01_basics": "Simple vertical alignment, heights and interactive status",
    "02_rows": "Nested horizontal rows, text gravity and spacing",
    "03_grid": "Grid cells, repeated controls and alignment variants",
    "04_nesting": "Deep alternating layout tree and inherited colors",
    "05_scroll": "Scrollable data, wrapping, buttons and fixed footer",
    "06_form": "Form editing, checkbox, switch, validation and confirmation",
    "07_sliders": "Coupled sliders, numeric labels and progress indicators",
    "08_states": "State transitions, toggle buttons and counter controls",
    "09_anchors": "Weight distribution, grid fill and text positioning",
    "10_overrides": "Nested semantic palettes and local hex overrides",
    "11_stress": "Long nested scroll lists, state feedback and repeatability",
    "12_studio": "Comprehensive live theme studio and color-scale picker",
    "13_workbench": "Complex interactive control dashboard with theme switching",
}


def panel(orientation="vertical", *, padding=8, spacing=5, **kwargs):
    return BoxLayout(orientation=orientation, padding=padding, spacing=spacing, **kwargs)


def label(text, **kwargs):
    return Label(text=str(text), font_size=kwargs.pop("font_size",16), **kwargs)


def row(*items, **kwargs):
    group=panel("horizontal",**kwargs)
    for item in items:group.add_widget(item)
    return group


def mix(a,b,amount):
    a=rgba_channels(a);b=rgba_channels(b)
    fraction=max(0.0,min(1.0,float(amount)))
    return "#"+''.join(f"{round((1-fraction)*x+fraction*y):02X}" for x,y in zip(a[:3],b[:3]))


class Laboratory(App):
    """Static widget tree, dynamic state, no unsupported insertion after render."""
    def __init__(self,scenario="12_studio",**kwargs):
        if scenario not in SCENARIOS:raise ValueError("unknown scenario: "+scenario)
        self.scenario=scenario
        self.counter=0
        self.selected="Idle"
        self.samples=[]
        self.levels=[]
        self.swatches=[]
        self._syncing_rgb=False
        super().__init__(**kwargs)

    def add_button(self,container,title,callback,**kwargs):
        button=Button(text=title,height=kwargs.pop("height",52),**kwargs)
        button.bind(on_release=lambda *_:callback())
        container.add_widget(button)
        return button

    def announce(self,text):
        self.selected=str(text)
        if hasattr(self,"status"):
            self.status.text=self.selected

    def _root(self,title):
        root=panel(spacing=7,padding=12)
        root.add_widget(label(title,font_size=22,height=54,halign="center"))
        root.add_widget(label(SCENARIOS[self.scenario],height=48,halign="center"))
        self.status=label("Ready. Exercise the controls.",height=55,halign="center",
                          colors={"text":"#F2CE52"})
        return root

    def _footer(self,root):
        root.add_widget(self.status)
        self.add_button(root,"Close",self.stop)
        return root

    def build(self):
        if self.scenario in ("12_studio","13_workbench"):
            return self._studio(workbench=self.scenario=="13_workbench")
        root=self._root("TGK layout lab — "+self.scenario)
        builder=getattr(self,"_build_"+self.scenario.split("_",1)[1])
        builder(root)
        return self._footer(root)

    def _build_basics(self,root):
        root.add_widget(label("LEFT / CENTER / RIGHT",height=44,halign="center"))
        for side in ("left","center","right"):
            self.add_button(root,"Align "+side,lambda side=side:self.announce(side),
                            halign=side)
        root.add_widget(label("Fixed footer remains below this content.",height=48))

    def _build_rows(self,root):
        for i in range(4):
            strip=row(spacing=6,padding=5,height=67)
            for side in ("left","center","right"):
                self.add_button(strip,f"{i+1}:{side}",lambda s=side,i=i:
                                self.announce(f"Row {i+1}, {s}"),halign=side)
            root.add_widget(strip)
        root.add_widget(label("Rows test equal weights and native child spacing."))

    def _build_grid(self,root):
        grid=GridLayout(cols=3,rows=4,height=370,colors={"surface":"#243145"})
        for index in range(12):
            self.add_button(grid,str(index+1),lambda i=index:self.announce(f"Cell {i+1}"),
                            align_row="fill" if index%2 else "center",
                            align_col="fill" if index%3 else "center")
        root.add_widget(grid)

    def _build_nesting(self,root):
        outer=panel(colors={"surface":"#1C3651"},padding=8)
        current=outer
        for depth in range(1,6):
            current.add_widget(label(f"Depth {depth}: alternating orientation",
                                     height=35))
            child=panel("horizontal" if depth%2 else "vertical",
                        colors={"surface":mix("#1C3651","#7B4FD6",depth/6)})
            current.add_widget(child)
            current=child
        self.add_button(current,"Deep event",lambda:self.announce("Nested callback reached root"))
        root.add_widget(outer)

    def _build_scroll(self,root):
        view=ScrollView(weight=1)
        data=panel(spacing=3)
        for i in range(50):
            self.add_button(data,f"Item {i:02d}: scroll and activate",
                            lambda i=i:self.announce(f"Selected item {i}"))
        view.add_widget(data)
        root.add_widget(view)

    def _build_form(self,root):
        self.name=TextInput(text="Sample",height=54,halign="left")
        self.note=TextInput(text="Edit me",height=54)
        root.add_widget(label("Name",height=32));root.add_widget(self.name)
        root.add_widget(label("Note",height=32));root.add_widget(self.note)
        self.enabled=CheckBox(text="Enabled",active=True,height=52)
        self.notify=Switch(text="Notify",active=False,height=52)
        root.add_widget(row(self.enabled,self.notify,height=62))
        self.add_button(root,"Validate",lambda:self.announce(
            f"Name={self.name.text!r}; note={self.note.text!r}; enabled={self.enabled.active}"))

    def _build_sliders(self,root):
        for index in range(4):
            p=panel(height=105,spacing=3)
            name=label(f"Channel {index+1}: 50",height=34)
            slider=Slider(min=0,max=100,value=50,step=1)
            progress=ProgressBar(value=50,height=20)
            slider.bind(value=lambda _w,v,name=name,progress=progress,index=index:
                        self._slider_update(index,name,progress,v))
            p.add_widget(name);p.add_widget(slider);p.add_widget(progress)
            root.add_widget(p)

    def _slider_update(self,index,name,progress,value):
        name.text=f"Channel {index+1}: {value:.0f}"
        progress.value=value
        self.announce(f"Channel {index+1} = {value:.0f}")

    def _build_states(self,root):
        self.state_label=label("Mode: idle | count: 0",height=56)
        root.add_widget(self.state_label)
        for action in ("start","pause","resume","reset"):
            self.add_button(root,action.title(),lambda s=action:self._transition(s))
        self.mode_toggle=ToggleButton(text="Toggle optional mode",state="normal")
        root.add_widget(self.mode_toggle)

    def _transition(self,action):
        if action=="reset":self.counter=0
        else:self.counter+=1
        self.state_label.text=f"Mode: {action} | count: {self.counter}"
        self.announce(f"Transition: {action}")

    def _build_anchors(self,root):
        root.add_widget(label("Text gravity inside fixed-height Views",height=34))
        for h,v in (("left","top"),("center","center"),("right","bottom")):
            root.add_widget(label(f"{h} / {v}",height=74,halign=h,valign=v,
                                  background_color="#34425C"))
        weighted=row(height=106,spacing=8)
        weighted.add_widget(label("WEIGHT 1",weight=1,halign="center",
                                  background_color="#2E6072"))
        weighted.add_widget(label("WEIGHT 2",weight=2,halign="center",
                                  background_color="#694A7D"))
        root.add_widget(weighted)

    def _build_overrides(self,root):
        outer=panel(colors={"surface":"#354A5E","text":"#F5D6B3"})
        outer.add_widget(label("Parent inherits custom text and surface",height=55))
        middle=panel(colors={"accent":"#FF6A55","button":"#8B3247"})
        middle.add_widget(label("Middle overrides accent / button",height=48))
        self.add_button(middle,"Inherited button",lambda:self.announce("Inherited"))
        self.add_button(middle,"Local cyan button",lambda:self.announce("Local"),
                        background_color="#087D93",text_color="#FFFFFF")
        outer.add_widget(middle);root.add_widget(outer)

    def _build_stress(self,root):
        scroll=ScrollView(weight=1)
        container=panel(spacing=2)
        for i in range(80):
            cell=row(height=58,spacing=3)
            cell.add_widget(label(f"{i:03d}",width=52))
            self.add_button(cell,"Action A",lambda i=i:self.announce(f"{i} A"))
            self.add_button(cell,"Action B",lambda i=i:self.announce(f"{i} B"))
            container.add_widget(cell)
        scroll.add_widget(container);root.add_widget(scroll)

    def _studio(self,workbench=False):
        root=self._root("TGK Theme Studio" if not workbench else "TGK Interactive Workbench")
        scroll=ScrollView(weight=1)
        content=panel(spacing=8,padding=10)
        content.add_widget(label("01 • PRESETS — tap to apply immediately",height=48))
        picker=GridLayout(cols=2,rows=6,height=380)
        for preset in PRESETS:
            theme=resolve_theme(preset)
            self.add_button(picker,preset.replace("_"," ").title(),
                            lambda preset=preset:self.pick(preset),
                            colors={"button":theme["surface"],"button_text":theme["text"]},
                            background_color=theme["primary"],
                            text_color=theme["text"])
        content.add_widget(picker)
        self.palette_name=label("Palette: "+self.theme.name,height=38,halign="center")
        content.add_widget(self.palette_name)
        content.add_widget(label("02 • SEMANTIC COLOR SCALE",height=40))
        self.swatches=[]
        for step in range(0,101,10):
            swatch=label(f"{step:3d}%  •  preview",height=28,
                         background_color=mix(self.theme["background"],self.theme["accent"],step/100),
                         halign="center")
            self.swatches.append((step,swatch))
            content.add_widget(swatch)
        content.add_widget(label("03 • CUSTOM HEX ROLE OVERRIDE",height=38))
        self.role_input=TextInput(text="accent",height=48)
        self.color_input=TextInput(text="#55DCE8",height=48)
        content.add_widget(row(self.role_input,self.color_input,height=58))
        self.add_button(content,"Apply semantic role override",self.apply_custom)
        content.add_widget(label("04 • LIVE ACCENT RGB SLIDERS",height=38))
        self.rgb_sliders=[]
        for index,channel in enumerate("RGB"):
            line=panel(height=91,spacing=0)
            line.add_widget(label(channel,height=28))
            slider=Slider(min=0,max=255,step=1,value=rgba_channels(self.theme["accent"])[index])
            slider.bind(value=lambda *_:self.update_rgb())
            self.rgb_sliders.append(slider);line.add_widget(slider);content.add_widget(line)
        content.add_widget(label("05 • NESTED BEHAVIOR & FORM STATE",height=40))
        self.input=TextInput(text="Edit this title",height=54)
        content.add_widget(self.input)
        self.check=CheckBox(text="Enable live feedback",active=True)
        content.add_widget(self.check)
        self.progress=ProgressBar(value=60,height=26)
        content.add_widget(self.progress)
        if workbench:
            content.add_widget(label("06 • WORKBENCH GRID: CONTROLS × ACTIONS",height=42))
            grid=GridLayout(cols=3,rows=4,height=330)
            for index in range(12):
                self.add_button(grid,f"Task {index+1}",lambda i=index:self.do_task(i))
            content.add_widget(grid)
            self.history=label("History: none",height=62)
            content.add_widget(self.history)
        controls=row(height=68,spacing=8)
        self.add_button(controls,"Apply title",lambda:self.announce(self.input.text))
        self.add_button(controls,"Reset theme",lambda:self.pick("midnight"))
        content.add_widget(controls)
        scroll.add_widget(content);root.add_widget(scroll)
        return self._footer(root)

    def _refresh_palette(self):
        if not hasattr(self,"palette_name"):return
        self.palette_name.text="Palette: "+self.theme.name+"   •   accent "+self.theme["accent"]
        for percent,swatch in self.swatches:
            swatch.background_color=mix(self.theme["background"],self.theme["accent"],percent/100)
            swatch.text_color="#000000" if percent>=65 else self.theme["text"]
        self.color_input.text=self.theme["accent"]
        self._syncing_rgb=True
        try:
            for index,slider in enumerate(self.rgb_sliders):
                slider.value=rgba_channels(self.theme["accent"])[index]
        finally:
            self._syncing_rgb=False
        self.announce("Active "+self.theme.name+" / "+self.theme["accent"])

    def pick(self,name):
        self.set_theme(name)
        self._refresh_palette()

    def apply_custom(self):
        try:
            role=self.role_input.text.strip()
            color=normalize_color(self.color_input.text.strip())
            self.set_theme(self.theme,**{role:color})
        except ValueError as exc:
            self.announce(f"Invalid override: {exc}")
            return
        self._refresh_palette()

    def update_rgb(self):
        if self._syncing_rgb or len(self.rgb_sliders)!=3 or not hasattr(self,"palette_name"):return
        channels=[int(slider.value) for slider in self.rgb_sliders]
        value="#"+''.join(f"{v:02X}" for v in channels)
        self.set_theme(self.theme,accent=value)
        for percent,swatch in self.swatches:
            swatch.background_color=mix(self.theme["background"],value,percent/100)
        self.palette_name.text="Custom accent "+value
        self.announce("Live accent "+value)

    def do_task(self,index):
        self.counter+=1
        self.progress.value=(self.counter*13)%101
        self.history.text=f"Action {index+1}: count={self.counter}, progress={self.progress.value}%"
        self.announce(f"Task {index+1}: {self.input.text}")


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo",choices=tuple(SCENARIOS),default="12_studio")
    parser.add_argument("--list",action="store_true")
    parser.add_argument("--theme",choices=tuple(PRESETS),default=get_theme().name)
    parser.add_argument("--color",action="append",default=[],metavar="ROLE=#HEX")
    args=parser.parse_args(argv)
    if args.list:
        for name,description in SCENARIOS.items():print(name+"  "+description)
        return 0
    overrides={}
    for item in args.color:
        if "=" not in item:parser.error("--color requires ROLE=#HEX")
        role,value=item.split("=",1)
        overrides[role.strip()]=value.strip()
    try:selected=resolve_theme(args.theme,overrides)
    except ValueError as exc:parser.error(str(exc))
    Laboratory(scenario=args.demo,theme=selected).run()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
