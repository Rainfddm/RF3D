import logging
from PyQt5.QtWidgets import QWidget,QVBoxLayout
import vtk
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

class CustomInteractorStyle(vtk.vtkInteractorStyleTrackballActor):
    """
    Custom interactor: Interaction style to move the actor
    """
    def __init__(self, parent=None):
        super().__init__()
        self.MotionFactor = 10.0
        self.axis_constraint = None  # 'x', 'y', or 'z'
        self.start_pos = None
        self.selected_actor = None
        self.is_dragging = False
        self.AddObserver("MiddleButtonPressEvent", self.MiddleButtonPressEvent)
        self.AddObserver("MiddleButtonReleaseEvent", self.MiddleButtonReleaseEvent)
        self.AddObserver("MouseMoveEvent", self.OnMouseMove)

    def MiddleButtonPressEvent(self, obj, event):
        self.OnMiddleButtonDown()
        self.start_pos = self.GetInteractor().GetEventPosition()
        logging.info(f"start_pos: {self.start_pos}")
        # 使用 picker 来确定点击的对象
        picker = vtk.vtkPropPicker()
        picker.Pick(self.start_pos[0], self.start_pos[1], 0,
                    self.GetInteractor().GetRenderWindow().GetRenderers().GetFirstRenderer())
        self.selected_actor = picker.GetActor()

        self.InvokeEvent(vtk.vtkCommand.StartInteractionEvent)
        return

    def MiddleButtonReleaseEvent(self, obj, event):
        self.OnMiddleButtonUp()
        if self.start_pos is not None:
            self.start_pos = None
            self.InvokeEvent(vtk.vtkCommand.EndInteractionEvent)
            self.GetInteractor().GetRenderWindow().SetCurrentCursor(vtk.VTK_CURSOR_DEFAULT)
        return


    def SetAxisConstraint(self, axis):
        self.axis_constraint = axis

    def OnMouseMove(self, obj, event):
        if not self.start_pos or not self.axis_constraint:
            return

        pos = self.GetInteractor().GetEventPosition()
        logging.info(f"move: {pos} ")


        dx = pos[0] - self.start_pos[0]
        dy = pos[1] - self.start_pos[1]
        move_vector = [0, 0, 0]

        if self.axis_constraint == 'x':
            move_vector = [-dx/self.MotionFactor, 0, 0]
        elif self.axis_constraint == 'y':
            move_vector = [0, -dy/self.MotionFactor, 0]
        elif self.axis_constraint == 'z':
            # Typically, vertical mouse movement might be chosen to affect the z-axis.
            move_vector = [0, 0, dy/self.MotionFactor]

        if self.selected_actor:
            current_pos = self.selected_actor.GetPosition()
            self.selected_actor.SetPosition(current_pos[0] + move_vector[0], current_pos[1] + move_vector[1],
                                         current_pos[2] + move_vector[2])
            self.GetInteractor().Render()

        self.InvokeEvent(vtk.vtkCommand.InteractionEvent)
        self.start_pos = pos


    def translate_actor(self, mouse_pos):
        # Implement the logic to translate the actor based on mouse movement
        # This function should translate the actor to the new position
        pass

class VTKViewer(QWidget):
    INTERACT_DEFAULT = 0
    INTERACT_MOVE = 1
    def __init__(self, parent=None):
        super(VTKViewer, self).__init__(parent)

        # Create a VTK render window interactor
        self.vtkWidget = QVTKRenderWindowInteractor(self)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.vtkWidget)
        self.setLayout(self.layout)

        # VTK Renderer
        self.renderer = vtk.vtkRenderer()
        self.vtkWidget.GetRenderWindow().AddRenderer(self.renderer)

        # Set up the interactor
        self.interactor = self.vtkWidget.GetRenderWindow().GetInteractor()
        self.interactor.Initialize()

        # Switchable interaction style
        self.customInteractStyle = CustomInteractorStyle()
        self.defaultInteractorStyle = vtk.vtkInteractorStyleTrackballCamera()
        # Set up the interaction style to vtkInteractorStyleTrackballCamera
        self.interactionStyle = self.defaultInteractorStyle
        self.interactor.SetInteractorStyle(self.interactionStyle)

        # Keep track of actors
        # Organizing actors in a dictionary
        self.actors = {
            "model":   [],
            "process": [],
            "layer": {},  # to check each layer
            "fixed": []   # 0: hotbet, 1: axis
        }

        # Keep track of command status
        self.status = {
            "InteractionStyle": self.INTERACT_DEFAULT
        }

        # Set up the picker
        self.picker = vtk.vtkPropPicker()

        # Connect the events
        self.interactor.AddObserver("LeftButtonPressEvent", self.on_click)
        self.interactor.AddObserver("KeyPressEvent", self.on_key_press)
        self.last_picked_actor = None

        # Init fixed parts
        self.__init_hotbed_grid()

    def get_data(self, actor_name, original=False):
        """
        Get data from the actor
        :param actor_name: is the actor's name
        :param original: False if get the transformed data by actor, True get the original data
        """
        # Get actor and mapper, only support model now.
        actors = self.actors[actor_name]
        if actor_name != "model":
            return None
        actor = actors[0]
        mapper = actor.GetMapper()
        if not mapper:
            logging.info("No mapper available for this actor.")
            return None

        # Get data from mapper
        data = mapper.GetInput()
        if not data:
            logging.info("No data available for this mapper.")
            return None

        # Check data
        if isinstance(data, vtk.vtkPolyData):
            if not original: # return transformed data
                transform = vtk.vtkTransform()
                transform.SetMatrix(actor.GetMatrix())
                # Create a transform filter
                transform_filter = vtk.vtkTransformPolyDataFilter()
                transform_filter.SetInputData(data)
                transform_filter.SetTransform(transform)
                transform_filter.Update()

                # Get transformed dta
                data = transform_filter.GetOutput()

            return data
        else:
            print("Data is not of type vtkPolyData.")
            return None
    def on_click(self, obj, event):
        if self.status["InteractionStyle"] == self.INTERACT_MOVE:
            click_pos = self.interactor.GetEventPosition()
            self.picker.Pick(click_pos[0], click_pos[1], 0, self.renderer)
            picked_actor = self.picker.GetActor()

            if picked_actor and picked_actor != self.actors["fixed"][1] and picked_actor != self.actors["fixed"][0]:
                if self.last_picked_actor:
                    self.last_picked_actor.GetProperty().SetEdgeColor(0, 0, 0)
                    self.last_picked_actor.GetProperty().SetLineWidth(1)
                self.last_picked_actor = picked_actor
                picked_actor.GetProperty().SetEdgeColor(1, 0, 0)
                picked_actor.GetProperty().SetEdgeVisibility(1)
                picked_actor.GetProperty().SetLineWidth(2)
                pos = picked_actor.GetPosition()
            elif self.last_picked_actor:
                self.reset_actor_properties(self.last_picked_actor)
                self.last_picked_actor = None

            self.interactor.Render()

    def reset_actor_properties(self, actor):
        """reset actor properties"""
        actor.GetProperty().SetEdgeColor(0, 0, 0)
        actor.GetProperty().SetEdgeVisibility(0)
        actor.GetProperty().SetLineWidth(1)

    def on_key_press(self, obj, event):
        key = self.interactor.GetKeySym()
        if key == "Escape":
            if self.last_picked_actor:
                self.reset_actor_properties(self.last_picked_actor)
                self.last_picked_actor = None

            obj.SetInteractorStyle(self.defaultInteractorStyle)
            self.status["InteractionStyle"] = self.INTERACT_DEFAULT
            logging.info("Switched to default mode.")

        elif key in ('x', 'y', 'z'):
            self.customInteractStyle.SetAxisConstraint(key)
            logging.info(f"Axis constrained to {key}.")

        elif key == 'm':
            # Switch to model movement mode
            obj.SetInteractorStyle(self.customInteractStyle)
            self.interactor.Render()
            self.status["InteractionStyle"] = self.INTERACT_MOVE
            logging.info("Switched to model movement mode.")

    # def on_mouse_move(self, obj, event):
    #     if self.status["InteractionStyle"] == self.INTERACT_MOVE:
    #         if self.is_dragging and self.last_picked_actor:
    #             # Get the current mouse position
    #             mouse_pos = self.interactor.GetEventPosition()
    #             new_pos = self.calculate_new_position(mouse_pos)
    #             self.last_picked_actor.SetPosition(new_pos)
    #             self.interactor.Render()
    @staticmethod
    def calculate_new_position(self, mouse_pos):
        # Implement logic to calculate new position based on mouse movement
        # Placeholder for demonstration
        return (mouse_pos[0] * 0.01, mouse_pos[1] * 0.01, 0)

    def __init_hotbed_grid(self):
        # 创建用于保存网格线的对象
        lines = vtk.vtkCellArray()
        points = vtk.vtkPoints()

        # 设置网格大小和间隔
        grid_size = 300
        spacing = 10

        start = int(-grid_size / 2)
        end = int(grid_size / 2)

        # 创建网格线
        for i in range(start, end + 1, spacing):
            # 创建 x 方向的线
            points.InsertNextPoint(i, start, 0)
            points.InsertNextPoint(i, end, 0)
            lines.InsertNextCell(2)
            lines.InsertCellPoint(points.GetNumberOfPoints() - 2)
            lines.InsertCellPoint(points.GetNumberOfPoints() - 1)

            # 创建 y 方向的线
            points.InsertNextPoint(start, i, 0)
            points.InsertNextPoint(end, i, 0)
            lines.InsertNextCell(2)
            lines.InsertCellPoint(points.GetNumberOfPoints() - 2)
            lines.InsertCellPoint(points.GetNumberOfPoints() - 1)

        # 创建一个 polydata 对象并将点和线添加进去
        grid = vtk.vtkPolyData()
        grid.SetPoints(points)
        grid.SetLines(lines)

        # 创建映射器和 actor
        gridMapper = vtk.vtkPolyDataMapper()
        gridMapper.SetInputData(grid)
        actor = vtk.vtkActor()
        # Set color to light yellow (RGB)
        light_yellow = [1.0, 1.0, 0.88]  # Light yellow color in RGB
        actor.GetProperty().SetColor(light_yellow)  # Set the color
        actor.GetProperty().SetOpacity(0.5)

        actor.SetMapper(gridMapper)   

        # Add the actor to the scene
        self.renderer.AddActor(actor)

        # Keep track of the actor
        self.actors["fixed"].append(actor)

        # Axis Actor
        def create_fixed_size_label(text, position):
            label_actor = vtk.vtkBillboardTextActor3D()
            label_actor.SetPosition(position)
            label_actor.GetTextProperty().SetFontSize(24)  # Set the size of the text
            label_actor.GetTextProperty().SetColor(1.0, 1.0, 1.0)  # White color
            label_actor.SetInput(text)
            return label_actor

        axis = vtk.vtkAxesActor()
        axes_label_size = 20
        axis.SetTotalLength(axes_label_size, axes_label_size, axes_label_size)  # Axis length

        axis.VisibilityOn()  # Initially hidden
        self.renderer.AddActor(axis)

        # Hide the default labels (Because size cannot be regulated)
        axis.SetAxisLabels(0)

        # Create and add custom labels
        x_label = create_fixed_size_label("X", [axes_label_size, 0, 0])
        y_label = create_fixed_size_label("Y", [0, axes_label_size, 0])
        z_label = create_fixed_size_label("Z", [0, 0, axes_label_size])
        self.renderer.AddActor(x_label)
        self.renderer.AddActor(y_label)
        self.renderer.AddActor(z_label)

        self.actors["fixed"].append(axis)
        self.actors["fixed"].append(x_label)
        self.actors["fixed"].append(y_label)
        self.actors["fixed"].append(z_label)

        #self.renderer.ResetCamera()
        self.setup_default_camera()
        
        self.interactor.Render()

    def Update(self):       
        self.interactor.Render()

    # return vtk_poly_data
    def loadSTL(self, filename):
        # Clear first
        self.clear("model")
        self.clear("process")
        self.clear("layer")
        # Read STL
        reader = vtk.vtkSTLReader()
        reader.SetFileName(filename)
        reader.Update()  # Ensure the reader reads the STL file

        # Get the center of the STL geometry
        bounds = reader.GetOutput().GetBounds()
        #center = [(bounds[i+1] + bounds[i]) / 2.0 for i in range(0, 6, 2)]
        center_x = (bounds[1] + bounds[0]) / 2.0
        center_y = (bounds[3] + bounds[2]) / 2.0
        min_z = bounds[4]  # Minimum Z coordinate

        # Create a transform to translate the STL to the origin
        transform = vtk.vtkTransform()
        transform.Translate(-center_x, -center_y, -min_z)

        # Create a filter to apply the transform
        transformFilter = vtk.vtkTransformPolyDataFilter()
        transformFilter.SetInputConnection(reader.GetOutputPort())
        transformFilter.SetTransform(transform)
        transformFilter.Update()

        # Create a mapper
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(transformFilter.GetOutputPort())

        # Create an actor
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)

        # Add the actor to the scene
        self.renderer.AddActor(actor)
        self.renderer.ResetCamera()
        self.interactor.Render()
        
        # Keep track of the actor
        self.actors["model"].append(actor)
        num_actors = self.count_actors_in_renderer()
        logging.info(f"Number of actors in the render: {num_actors}")

        # Return vtk_poly_data
        vtk_poly_data = transformFilter.GetOutput()
        return vtk_poly_data
        
    def clear(self, actor_type=None):
        # Remove all actors from the renderer beside hotbed
        # Remove layer first
        if actor_type == "layer" or actor_type == None:
            for key in self.actors["layer"]:
                actors = self.actors["layer"].get(key)
                for a in actors:
                    self.renderer.RemoveActor(a)
            self.actors["layer"].clear()
            
        if (actor_type is None):            
            # Remove others
            for key in self.actors:
                for actor in self.actors[key]:
                    self.renderer.RemoveActor(actor)
                self.actors[key].clear()    
        else:                        
            for actor in self.actors[actor_type]:
                self.renderer.RemoveActor(actor)
            self.actors[actor_type].clear()
        self.interactor.Render()
        
    def clear_layer(self, key):
        actors = self.actors["layer"].get(key)
        if actors is not None:
            for a in actors:
                self.renderer.RemoveActor(a)
        self.actors["layer"].pop(key, None)
        
    def add_polylines(self, polylines, color=(0,0,1), line_width=2):
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polylines)

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)

        # Set polyline color
        actor.GetProperty().SetColor(color)  # Color in RGB format

        # Set polyline width
        actor.GetProperty().SetLineWidth(line_width)

        # Add the actor to the scene
        self.renderer.AddActor(actor)
        self.interactor.Render()

        self.actors["process"].append(actor)
        return actor

    def add_polyline(self, polyline, color=(0,1,0), line_width=4):        
    
        # Create a mapper and actor
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polyline)
    
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)

        # Set polyline color
        actor.GetProperty().SetColor(color)  # Color in RGB format

        # Set polyline width
        actor.GetProperty().SetLineWidth(line_width)
    
        # Add the actor to the renderer and render
        self.renderer.AddActor(actor)
        self.interactor.Render()        
        
        return actor
    
    def setup_default_camera(self, position=(300, 300, 300), view_up=(0, 0, 1)):
        # Get the current camera
        camera = self.renderer.GetActiveCamera()
        
        # Set the camera position
        camera.SetPosition(position[0], position[1], position[2])

        # Set the focal point to the origin (0, 0, 0)
        camera.SetFocalPoint(0, 0, 0)

        # Optional: Set up the camera's up direction (e.g., y-axis)
        camera.SetViewUp(view_up[0], view_up[1], view_up[2])

        # Update the camera
        self.renderer.ResetCamera()
        self.interactor.Render()

    
    def set_display_mode(self, mode):
        for actor in self.actors["model"]:
            if mode == "Wireframe":
                actor.GetProperty().SetRepresentationToWireframe()
            elif mode == "Solid":
                actor.GetProperty().SetRepresentationToSurface()            
            else:
                actor.GetProperty().SetRepresentationToSurface()  # Default to solid
            

        self.interactor.Render()
     
    def set_transparancy(self, value):
         
        for actor in self.actors["model"]:
            actor.GetProperty().SetOpacity(value)   
        
        self.interactor.Render()

    def count_actors_in_renderer(self):
        # Get the collection of actors from the renderer
        actors_collection = self.renderer.GetActors()
        
        # Count the number of actors
        count = actors_collection.GetNumberOfItems()

        return count    


