import open3d as o3d
from Simulator2.o3dElements import gui, rendering
import threading
import Simulator2.Layout as Layout
import sys
import time
import Simulator2.Nodes as Nodes

o3d.utility.set_verbosity_level(o3d.utility.VerbosityLevel.Debug)
o3d.utility.set_verbosity_level(o3d.utility.VerbosityLevel.Error)


class BaseSimulator:
    """
    Base class for Simulator

    ...

    Public Attributes
    ----------
    title: str
        the title of current window
    width: int
        the width of the window
    height: int
        the height of the window
    animation_delay_time: float
        the min time between each frame
    scene: open3d.visualization.gui.SceneWidget
        The Active scene used to render 3D objects
    em: float
        The current font-size
    panel: Simulator2.Layout.Panel
        Panel object that extends from gui.Vert

    Private Attributes
    ------------------
    _last_animation_time: float
        The last time a frame was processed.
    _computational_nodes: list
        List of Node objects that are registered with the Base Simulator. Registering a Node will cause it be updated
        each frame
    _state: threading.Condition
        Condition state to manage if thread should stop or continue
    _paused: bool
        bool value that indicates if simulator is paused
    _running: threading.Event
        Event object that is used to exit computational thread
    _computational_thread: threading.Thread
        Current active thread for computation. Only 1 thread is active at a time and is closed when window is closed
    """
    def __init__(self, title: str, width: int, height: int):
        gui.Application.instance.initialize()

        self.title = title
        self.width = width
        self.height = height
        self._last_animation_time = 0.0
        self.animation_delay_time = 2.0

        self.window = gui.Application.instance.create_window(title, width, height)
        self.window.set_on_layout(self._on_layout)
        self.window.set_on_close(self._quit)
        self.scene = gui.SceneWidget()
        self.scene.scene = rendering.Open3DScene(self.window.renderer)

        self.scene.scene.set_background([0, 0, 0, 1])
        self.scene.scene.scene.set_sun_light(
            [-1, -1, -1],  # direction
            [1, 1, 1],  # color
            100000)  # intensity
        self.scene.scene.scene.enable_sun_light(True)

        self.scene.set_on_key(self._on_key)
        self.scene.set_on_mouse(self._on_mouse_3d)
        self.scene.scene.show_ground_plane(True, rendering.Scene.GroundPlane.XZ)
        self.window.add_child(self.scene)

        bbox = o3d.geometry.AxisAlignedBoundingBox([-10, -10, -10],
                                                   [10, 10, 10])
        self.scene.setup_camera(90, bbox, [0, 0, 0])

        self.em = self.window.theme.font_size
        self.panel = Layout.Panel(self.em)
        self.window.add_child(self.panel)

        self._computational_nodes = []

        self._state = threading.Condition()
        self._paused = True
        self._running = threading.Event()

        self._computational_thread = threading.Thread(target=self._run_computational_loop)

    def register_node(self, n):
        """
        Registers a Node with the Simulator (Append node to self._computational_nodes)

        Parameters
        ----------
        n: Simulator2.Nodes.HeadlessNode
            The Node that is to be appended to active list of computation_nodes
            Visual Nodes can either be added to Panel or the Window.
        """
        n.simulator = self
        self._computational_nodes.append(n)
        if isinstance(n, Nodes.VisualNode):
            if n.register:
                self.panel.add_fixed(self.em)
                self.panel.add_child(n)
            else:
                self.window.add_child(n)

    def get_nodes(self, cl: Nodes.HeadlessNode):
        """
        Returns Nodes of a specified type

        Parameters
        ----------
        cl: Simulator2.Nodes.*
            Type of Node, input is HeadlessNode because headless is base class
        """
        temp = []
        for node in self._computational_nodes:
            if isinstance(node, cl):
                temp.append(node)
        return temp

    def on_start(self):
        for node in self._computational_nodes:
            node.on_start()

    def on_exit(self):
        for node in self._computational_nodes:
            node.on_exit()

    def run(self):
        self.on_start()
        self.scene.force_redraw()
        gui.Application.instance.run()

    def _on_mouse_3d(self, event):
        for node in self._computational_nodes:
            result = node.on_mouse_3d(event)
            if result == gui.Widget.EventCallbackResult.HANDLED:
                return result
        return gui.Widget.EventCallbackResult.IGNORED

    def _on_key(self, event):
        for node in self._computational_nodes:
            result = node.on_key(event)
            if result == gui.Widget.EventCallbackResult.HANDLED:
                return result
        return gui.Widget.EventCallbackResult.IGNORED

    def _quit(self):
        self.on_exit()

        for thread in threading.enumerate():
            print(thread.name)

        if self._running.is_set():
            self._running.clear()
            self._computational_thread.join()

        self._computational_nodes.clear()

        gui.Application.instance.quit()

    def _on_layout(self, layout_context):
        for node in self._computational_nodes:
            if isinstance(node, Nodes.VisualNode):
                node.create_layout(layout_context)

        frame = self.window.content_rect
        panel_rect = self.panel.setup_layout(self.window)
        self.scene.frame = gui.Rect(frame.x, frame.y, panel_rect.x - frame.x, frame.height - frame.y)

    def _run_computational_loop(self):
        self._last_animation_time = 0.0
        self.main_thread_finished = True
        while self._running.is_set():
            now = time.time()
            if self.main_thread_finished and now >= self._last_animation_time + self.animation_delay_time:
                self._last_animation_time = now

                # gui.Application.instance.run_one_tick()
                def display():
                    for node in self._computational_nodes:
                        if isinstance(node, Nodes.VisualNode):
                            node.step()
                    self.main_thread_finished = True

                for node in self._computational_nodes:
                    if not isinstance(node, Nodes.VisualNode):
                        node.step()

                self.main_thread_finished = False
                gui.Application.instance.post_to_main_thread(self.window, display)
                # print(time.time() - self._last_animation_time)
            else:
                time.sleep(now - self._last_animation_time - self.animation_delay_time)

    def start_computational_thread(self):

        if not self._running.is_set():

            for node in self._computational_nodes:
                node.on_start_computation_thread()
            self._computational_thread = threading.Thread(target=self._run_computational_loop)

            self._running.set()
            self._computational_thread.start()

    def stop_computational_thread(self):
        self._running.clear()
        self._computational_thread.join()

        for node in self._computational_nodes:
            node.on_pause_computational_thread()


if __name__ == "__main__":
    base = BaseSimulator("Base", 1920, 1080)
    base.run()
