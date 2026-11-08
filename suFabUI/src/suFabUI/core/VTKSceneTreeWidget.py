import vtk
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from PyQt5.QtWidgets import QTreeView, QTreeWidget, QTreeWidgetItem, QApplication
from PyQt5.QtCore import Qt

# class VTKSceneTreeWidget(QTreeWidget):
#     def __init__(self, vtkRenderWindowInteractor, parent=None):
#         super(VTKSceneTreeWidget, self).__init__(parent)
#
#         self.vtkRenderWindowInteractor = vtkRenderWindowInteractor
#         self.setHeaderLabels(["Actor", "Visibility"])
#         self.populateTree()
#         self.itemChanged.connect(self.onItemChanged)
#
#     def populateTree(self):
#         renderer = self.vtkRenderWindowInteractor.GetRenderWindow().GetRenderers().GetFirstRenderer()
#         actors = renderer.GetActors()
#         actors.InitTraversal()
#
#         for i in range(actors.GetNumberOfItems()):
#             actor = actors.GetNextActor()
#             item = QTreeWidgetItem(self)
#             item.setText(0, actor.GetClassName())
#             item.setCheckState(1, Qt.Checked if actor.GetVisibility() else Qt.Unchecked)
#             item.setData(0, Qt.UserRole, actor)
#
#     def onItemChanged(self, item, column):
#         if column == 1:
#             actor = item.data(0, Qt.UserRole)
#             if(actor is not None):
#                 actor.SetVisibility(item.checkState(1) == Qt.Checked)
#                 self.vtkRenderWindowInteractor.GetRenderWindow().Render()


class VTKSceneTreeWidget(QTreeWidget):
    def __init__(self, vtk_viewer, parent=None):
        super(VTKSceneTreeWidget, self).__init__(parent)
        self.vtk_viewer = vtk_viewer
        # self.setColumnCount(2)
        self.setHeaderLabels(["Actor", "Visibility"])
        self.init_tree()
        self.itemChanged.connect(self.onItemChanged)
    
    def init_tree(self):
        self.root_items = {}
        actor_types = ["model", "process", "layer", "fixed"]
        for actor_type in actor_types:
            root_item = QTreeWidgetItem(self, [actor_type.title()])
            self.root_items[actor_type] = root_item
            self.addTopLevelItem(root_item)
            if actor_type != "layer":
                for actor in self.vtk_viewer.actors[actor_type]:
                    self.add_actor_to_tree(actor_type, actor)
            else:
                for layer_name, layer_actors in self.vtk_viewer.actors["layer"].items():
                    layer_item = QTreeWidgetItem(root_item, [layer_name])
                    root_item.addChild(layer_item)
                    for actor in layer_actors:
                        actor_item = QTreeWidgetItem(layer_item, [str(actor)])
                        layer_item.addChild(actor_item)

    def add_actor_to_tree(self, actor_type, actor):
        parent_item = self.root_items[actor_type]
        item = QTreeWidgetItem(self)
        item.setText(0, actor_type)
        item.setCheckState(1, Qt.Checked if actor.GetVisibility() else Qt.Unchecked)
    #   item.setData(0, Qt.UserRole, actor)
        parent_item.addChild(item)

    def remove_actor_from_tree(self, actor_type, actor):
        parent = self.root_items[actor_type]
        for i in range(parent.childCount()):
            if parent.child(i).text(0) == str(actor):
                child = parent.takeChild(i)
                del child
                break

    def onItemChanged(self, item, column):
        if column == 1:
            actor = item.data(0, Qt.UserRole)
            if actor is not None:
                actor.SetVisibility(item.checkState(1) == Qt.Checked)
                self.vtk_viewer.Render()

    def updateTreeView(self):
        pass