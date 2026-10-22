from pathlib import Path
from kivy.app import App
from kivy.lang import Builder

class DemoApp(App):
    def build(self):
        return Builder.load_file(Path(__file__).with_suffix('.kv'))
    def update_status(self):
        self.root.ids.status.text = self.root.ids.usertext.text
    def update_slider(self, value):
        self.root.ids.slider_status.text = f'Level: {value:.0f}'
        self.root.ids.level_progress.value = value

if __name__=='__main__':DemoApp().run()
