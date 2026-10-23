"""Advanced TGK lab: tabs, screens, popup, rich text, icons and infinite canvas.

Run: python examples/advanced_gui.py --mode normal|dialog|overlay --theme ocean
An Android overlay requires Termux:GUI "Display over other apps" permission.
This is a finite-size framebuffer over unbounded mathematical coordinates.
"""
import argparse

from tgk import (
    App, BoxLayout, FloatLayout, ScrollView, GridLayout, Label, Button,
    Screen, ScreenManager, Tab, TabbedPanel, Popup, InfiniteCanvas,
    RichTextLabel, IconLabel, TextSpan, ICONS, CATEGORIES,
    resolve_theme, PRESETS_TEXT,
)


class AdvancedLab(App):
    def build(self):
        from tgk.layout_helpers import compact_action_bar
        root=BoxLayout(orientation="vertical")
        layer=FloatLayout(weight=1)
        self.tabs=TabbedPanel(height=740)
        self.message=Label(text="Explore tabs, then open the popup.",height=42)
        main=self._make_home()
        self.tabs.add_widget(main)
        self.tabs.add_widget(self._make_icons())
        self.tabs.add_widget(self._make_typography())
        self.tabs.add_widget(self._make_canvas())
        self.tabs.add_widget(self._make_pages())
        layer.add_widget(self.tabs)

        self.popup=Popup(visible=False,width=320,height=230,
                         background_color="#29395B",padding=8,spacing=6)
        self.popup.add_widget(Label(text="Modal-like View Overlay",height=45,
                                    font_size=20))
        self.popup.add_widget(RichTextLabel(
            text="This overlay is rendered inside the current Android Activity. "
                 "It remains allocated while hidden, with no destructive rebuild.",
            style="small",height=95))
        self._button(self.popup,"Dismiss",self.popup.dismiss)
        layer.add_widget(self.popup)
        root.add_widget(layer)
        root.add_widget(compact_action_bar("Close",self.stop,margin=12))
        return root

    def _button(self,group,text,callback):
        from tgk.layout_helpers import action_width
        b=Button(text=text,height=48,width=action_width(text))
        b.bind(on_release=lambda *_:callback())
        group.add_widget(b)
        return b

    def _make_home(self):
        tab=Tab(name="home",title="Home",padding=9,spacing=8)
        tab.add_widget(Label(text="MULTI-VIEW / POPUPS / ICONS",height=70,
                             font_size=22))
        tab.add_widget(self.message)
        self._button(tab,"Show In-Activity Popup",lambda:self.popup.open())
        self._button(tab,"Cycle Palette",self.cycle_theme)
        self._button(tab,"Go to Icon Catalog",lambda:self.tabs.switch("icons"))
        self._button(tab,"Go to Infinite Canvas",lambda:self.tabs.switch("canvas"))
        return tab

    def cycle_theme(self):
        from tgk.theme import PRESETS
        names=list(PRESETS)
        idx=names.index(self.theme.name)
        self.set_theme(names[(idx+1)%len(names)])
        self.message.text="Active palette: "+self.theme.name

    def _make_icons(self):
        tab=Tab(name="icons",title="Icons")
        tab.add_widget(Label(text=f"{len(ICONS)} semantic symbols • Unicode fallback",height=44))
        scroll=ScrollView(weight=1)
        grid=GridLayout(cols=2,rows=0)
        for group,keys in CATEGORIES.items():
            for name in keys[:30]:
                item=IconLabel(icon=name,text=name,font_size=13,height=45)
                grid.add_widget(item)
        scroll.add_widget(grid);tab.add_widget(scroll)
        return tab

    def _make_typography(self):
        tab=Tab(name="type",title="Typography")
        tab.add_widget(Label(text="SAFE FORMATTED TEXT",height=48))
        scroll=ScrollView(weight=1)
        stack=BoxLayout(orientation="vertical",padding=7,spacing=7)
        stack.add_widget(RichTextLabel(
            spans=[TextSpan("Bold title: ",style="title"),
                   TextSpan("italic ",style="quote",color="#B18EFF"),
                   TextSpan("underlined link color",style="link"),
                   TextSpan("\nInline code / <script> safely escaped",style="code")],
            height=200))
        for name in PRESETS_TEXT:
            stack.add_widget(RichTextLabel(text=f"{name}: The quick brown fox. 123 ÅÜé",
                                          style=name,height=74))
        scroll.add_widget(stack);tab.add_widget(scroll)
        return tab

    def _make_canvas(self):
        tab=Tab(name="canvas",title="Canvas",padding=5)
        tab.add_widget(Label(text="Drag to pan • pinch with two fingers to zoom",height=49))
        self.viewport=InfiniteCanvas(width=512,height=384,zoom=1.0)
        for i in range(-7,8):
            self.viewport.add_marker(i*120,(i*i%9-4)*65,
                                     role="accent" if i%2 else "success")
        tab.add_widget(self.viewport)
        buttons=BoxLayout(orientation="horizontal",height=62)
        self._button(buttons,"Zoom +",lambda:self.viewport.zoom_at(1.5))
        self._button(buttons,"Zoom −",lambda:self.viewport.zoom_at(1/1.5))
        self._button(buttons,"Center",lambda:self.reset_canvas())
        tab.add_widget(buttons)
        return tab

    def reset_canvas(self):
        self.viewport.center_x=0
        self.viewport.center_y=0
        self.viewport.zoom=1

    def _make_pages(self):
        tab=Tab(name="pages",title="Pages")
        tab.add_widget(Label(text="Second nested multi-view stack",height=50))
        self.pages=ScreenManager(current="alpha")
        for key in ("alpha","beta","gamma"):
            screen=Screen(name=key,title=key.title())
            screen.add_widget(Label(text="Page "+key.upper(),height=120,font_size=25))
            self._button(screen,"Next nested view",lambda:self.pages.next())
            screen.add_widget(IconLabel(icon="folder",text="Nested icon and state"))
            self.pages.add_widget(screen)
        tab.add_widget(self.pages)
        return tab


def main():
    from tgk.theme import PRESETS
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=("normal","dialog","overlay"),default="normal")
    p.add_argument("--theme",choices=tuple(PRESETS),default="midnight")
    args=p.parse_args()
    AdvancedLab(theme=args.theme,window_mode=args.mode).run()


if __name__=="__main__":main()
