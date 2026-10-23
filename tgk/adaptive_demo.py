"""Responsive Android 12-column layout and styling demonstration.

Run: python examples/adaptive_layout.py --theme ocean --orientation system
Rotate the phone to change the grid geometry without rebuilding native Views.
"""
import argparse

from tgk import (App,BoxLayout,ScrollView,ResponsiveGrid,Button,Label,
                 RichTable,Slider,ProgressBar,resolve_theme,PRESETS,
                 TextInput,ScreenMetrics,LayoutScale)
from tgk.style_tokens import TableStyle


class AdaptiveLab(App):
    def build(self):
        root=BoxLayout(orientation="vertical",padding=8,spacing=6)
        root.add_widget(Label(text="TGK • ADAPTIVE 12-COLUMN UI",height=52,
                              text_style="title_h3",halign="center"))
        self.status=Label(text="Reading Android window configuration...",height=52,
                          text_style="metadata",halign="center")
        root.add_widget(self.status)
        scroll=ScrollView(weight=1)
        body=BoxLayout(orientation="vertical",padding=6,spacing=7)
        intro=Label(text="Rotate: compact/medium/expanded grid spans",
                    height=48,halign="center")
        body.add_widget(intro)
        grid=ResponsiveGrid()
        for index in range(18):
            btn=Button(text=f"Card {index+1:02d}",span_compact=12,
                       span_medium=6,span_expanded=4,
                       visual_state=("active" if index%7==0 else "normal"))
            btn.bind(on_release=lambda _sender,i=index:self.click_card(i))
            grid.add_widget(btn)
        body.add_widget(grid)
        body.add_widget(Label(text="Button state variants",height=48,
                              text_style="title_h4"))
        button_states=ResponsiveGrid()
        for name in ("normal","pressed","active","disabled"):
            btn=Button(text=name.title(),span_compact=6,
                       span_medium=3,span_expanded=3,visual_state=name)
            btn.bind(on_release=lambda _sender,value=name:self.status_update(value))
            button_states.add_widget(btn)
        body.add_widget(button_states)
        body.add_widget(Label(text="Table with alternating row/column shading",
                              height=48,text_style="title_h4"))
        table=RichTable(rows=[
            ["Column","Metric","Value"],
            ["Device","12-column grid","responsive"],
            ["Touch","Minimum target","48 dp"],
            ["Color","Theme","semantic"],
            ["Orientation","Mode",self.orientation_mode],
            ["Refresh rate","Hardware max","not provided by binding"]
        ],height=340,table_style=TableStyle(
            shade_alternate_rows=True,shade_alternate_columns=True,
            first_column_right_width_dp=3,header_bottom_width_dp=4,
            bold_first_column=True))
        body.add_widget(table)
        body.add_widget(Label(text="Theme selection (live semantics)",height=42,
                              text_style="title_h4"))
        themes=ResponsiveGrid()
        for name in list(PRESETS)[:8]:
            btn=Button(text=name,span_compact=6,
                       span_medium=4,span_expanded=3)
            btn.bind(on_release=lambda _sender,name=name:self.change_theme(name))
            themes.add_widget(btn)
        body.add_widget(themes)
        body.add_widget(Label(text="Input and progress",height=40,
                              text_style="title_h4"))
        field=TextInput(text="Editable, touch sized",height=52)
        body.add_widget(field)
        value=Label(text="70%",height=28)
        slider=Slider(value=70,step=1)
        progress=ProgressBar(value=70,height=22)
        slider.bind(value=lambda _sender,v:self.update_progress(v,value,progress))
        body.add_widget(value);body.add_widget(slider);body.add_widget(progress)
        scroll.add_widget(body);root.add_widget(scroll)
        close=Button(text="Close",height=54)
        close.bind(on_release=lambda *_:self.stop())
        root.add_widget(close)
        return root

    def on_start(self):
        backend=self._backend
        metrics=getattr(backend,'screen_metrics',None)
        self.status.text=(f"{metrics.width_dp:g}×{metrics.height_dp:g} dp • "
                          f"{metrics.orientation} • {metrics.size_class}"
                          if metrics else "Android window metrics unavailable")

    def click_card(self,i):
        self.status.text=f"Card {i+1} selected"

    def status_update(self,state):
        self.status.text="State: "+state

    def change_theme(self,name):
        self.set_theme(name)
        self.status.text="Theme: "+name

    def update_progress(self,value,label,bar):
        label.text=f"{value:.0f}%"
        bar.value=value


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--theme",choices=tuple(PRESETS),default="midnight")
    parser.add_argument("--orientation",choices=("system","portrait","landscape"),
                        default="system")
    parser.add_argument("--touch-target-dp",type=int,default=48)
    parser.add_argument("--grid-unit-dp",type=int,default=4)
    args=parser.parse_args()
    scale=LayoutScale(touch_target_dp=args.touch_target_dp,
                      grid_unit_dp=args.grid_unit_dp)
    AdaptiveLab(theme=args.theme,orientation_mode=args.orientation,
                layout_scale=scale).run()


if __name__=="__main__":main()
