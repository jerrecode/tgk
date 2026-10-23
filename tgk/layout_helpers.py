"""Compact, right-aligned mobile action rows with bounded touch geometry.

Termux:GUI's FrameLayout has no exposed layout-gravity setter; a horizontal
LinearLayout with a weighted spacer produces an actual bottom/right aligned
button when used as the final child of a vertical root. This is native
layout behavior, not hard-coded screen coordinates.
"""
from .widgets import BoxLayout, Button, Widget


def action_width(text,*,minimum=64,maximum=224,side_padding=20,char_dp=8):
    if not isinstance(text,str):raise TypeError("text must be a string")
    if not text:raise ValueError("button text cannot be empty")
    if type(minimum) is not int or type(maximum) is not int or minimum<48 or maximum<minimum:
        raise ValueError("invalid action width bounds")
    return min(maximum,max(minimum,len(text)*char_dp+side_padding*2))


def compact_action_bar(label="Close",callback=None,*,margin=12,
                       height=48,button_width=None,button_role="cancel"):
    """Right-align a fixed-size action with empty weighted space on its left."""
    if type(margin) is not int or not 0<=margin<=48:
        raise ValueError("margin must be in 0..48dp")
    if type(height) is not int or not 48<=height<=96:
        raise ValueError("height must be in 48..96dp")
    width=button_width if button_width is not None else action_width(label)
    if type(width) is not int or not 48<=width<=320:raise ValueError("invalid width")
    bar=BoxLayout(orientation="horizontal",height=height+margin*2,padding=margin)
    spacer=Widget(weight=1)
    button=Button(text=label,width=width,height=height,
                  component_style="button",visual_state="normal")
    button.action_role=button_role
    if callback is not None:button.bind(on_release=lambda *_:callback())
    bar.add_widget(spacer)
    bar.add_widget(button)
    return bar
