from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas # type: ignore
from matplotlib.figure import Figure # type: ignore
from PyQt5.QtWidgets import (QVBoxLayout, 
                             QWidget, 
                             QScrollArea, 
                             QSizePolicy, 
                             QSpacerItem, 
                             QHBoxLayout, 
                             QPushButton)
import time

class IndividualPlotView(QWidget):
    def __init__(self, parent, width=6, height=2, dpi=100, signal=None, label="", indices=[], xlim=[0, 1000], model=None, id=None, controls=True):
        self.fig = Figure(figsize=(width, height), dpi=dpi)           
        super().__init__(parent)

        self.model = model
        self.block_id = id

        # Create the figure and canvas
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.updateGeometry()

        self.axes = self.fig.add_subplot(111)
        self.line = None    # Plot line
        self.indicies_lines = []    # lines of indicies
        self.initialize_plot(signal, label, indices, xlim)

        # Set a fixed height for the plot
        self.setFixedHeight(height * dpi)

        # Create the main layout
        layout = QHBoxLayout()

        # Create the controls widget
        self.control_widget = QWidget()
        controls_layout = QVBoxLayout()
        self.control_widget.setLayout(controls_layout)
        self.init_controls(controls_layout, controls)

        # Add widgets to main layout
        layout.addWidget(self.canvas)
        layout.addWidget(self.control_widget)

        self.setLayout(layout)

    def initialize_plot(self, signal, label, indices, xlim):
        """Initial the plot"""
        if signal:
            self.line, = self.axes.plot(range(len(signal)), signal, label=label)
            self.axes.set_xlim(xlim)
            for index in indices:
                line = self.axes.axvline(x=index, color='r', linestyle='-')
                self.indicies_lines.append(line)    # Store each vertical line
            if label:
                self.axes.set_title(label)

    def update_signal(self, new_signal, new_indices=None):
        """Update the plot with the new signal"""
        if self.line is not None:
            self.line.set_ydata(new_signal)
            self.line.set_xdata(range(len(new_signal)))
            self.axes.relim()
            self.axes.autoscale_view()
                                
        if new_indices is not None:
            # Remove old indicies
            for line in self.indicies_lines:
                line.remove()
            self.indicies_lines.clear()

            # Add new indices
            for index in new_indices:
                line = self.axes.axvline(x=index, color='r', linestyle='-')
                self.indicies_lines.append(line)

        self.fig.canvas.draw_idle()     # redraw the plot

    def init_controls(self, controls_layout, controls=True):
        """If related to a process block, then  add controls, otherwise don't"""
        if self.model:
                
            # Only add these controls if the widget is not the base widget
            if controls:
                move_up_button = QPushButton("Move Up")
                move_up_button.clicked.connect(self.move_up)
                controls_layout.addWidget(move_up_button)

                move_down_button = QPushButton("Move Down")
                move_down_button.clicked.connect(self.move_down)
                controls_layout.addWidget(move_down_button)

                remove = QPushButton("Remove")
                remove.clicked.connect(self.remove_filter)
                controls_layout.addWidget(remove)

            options = QPushButton("Options")
            options.clicked.connect(self.open_settings)
            controls_layout.addWidget(options)

    def move_up(self):
        if self.model:
            self.model.move_filter_up(self.block_id)

    def move_down(self):
        if self.model:
            self.model.move_filter_down(self.block_id)
    
    def remove_filter(self):
        print("remove triggered")
        if self.model:
            self.model.remove_by_id(self.block_id)

    def open_settings(self):
        if self.model:
            self.model.open_filter_settings(self.block_id)

class PipelineViewer(QWidget):

    def __init__(self, parent=None, model=None):
        super().__init__(parent)
        self.model = model
        self.plotViews = {}     # block id to plot view mapping

        self.init_UI()
        self.update()

        self.model.set_observer(self)   # Register as an observer

    def init_UI(self):
        self.scrollArea = QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)

        # Container for the plots
        self.plotContainerWidget = QWidget()
        self.plotLayout = QVBoxLayout(self.plotContainerWidget)
        self.scrollArea.setWidget(self.plotContainerWidget)

        # Main layout for this widget to include the scroll area
        mainLayout = QVBoxLayout(self)
        mainLayout.addWidget(self.scrollArea)
        self.setLayout(mainLayout)

        # Set the size policy to make the widget expanding
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))

        # Ensure the scroll area expands fully within SignalPlotView
        self.scrollArea.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)   # take the first item in the layout
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
            else:
                # Recursively clear any nested layouts
                nestedLayout = item.layout()
                if nestedLayout:
                    self.clearLayout(nestedLayout)
                # Remove spacer items or other non-widget items
                else:
                    del item

    def update(self):
        
        self.clear_layout(self.plotLayout)
        self.clean_up()     # Delete stray plots after a block as been deleted

        # Create individual plots for each signal
        curr = self.model.pipeline_start

        while curr:
            plotView = self.plotViews.get(curr.info['uuid'])
            if plotView is None:
                #Create the view
                controls = True
                if curr.info['name'] == 'Base':
                    controls = False
                plotView = IndividualPlotView(parent=self.plotContainerWidget,
                                              signal=curr.signal,
                                              label=curr.info['name'],
                                              indices=curr.indicies,
                                              xlim=[0, 1000],
                                              model=self.model,
                                              id=curr.info['uuid'],
                                              controls=controls)
                self.plotViews[curr.info['uuid']] = plotView
                curr.add_observer(plotView)
            else:
                plotView.show()
            self.plotLayout.addWidget(plotView)

            curr = curr.next_filter
            time.sleep(.125)
        
        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.plotLayout.addSpacerItem(spacer)

    def clean_up(self):

        uuids = []
        curr = self.model.pipeline_start
        if curr:
            while curr:
                uuids.append(curr.info['uuid'])
                curr = curr.next_filter

            for k in self.plotViews.keys():
                if k not in uuids:
                    del self.plotViews[k]
                    return
        



