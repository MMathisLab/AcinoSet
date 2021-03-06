import sys 
import numpy as np
import cv2

#GUI
from PyQt5.QtWidgets import QApplication, QGridLayout, QSizePolicy
from PyQt5 import QtGui, QtCore
import pyqtgraph.opengl as gl
import pyqtgraph
pyqtgraph.setConfigOption('background', 'w')
pyqtgraph.setConfigOption('foreground', 'k')
pyqtgraph.setConfigOptions(antialias=True) # antialias options have been included below so perhaps remove this?

#MPL
import matplotlib.pyplot as plt
# plt.rcParams['figure.dpi'] = 250 # to change the size of mpl plots
from matplotlib import collections  as mc
## The imports below appears to be unused - remove when certain
# from mpl_toolkits.mplot3d import Axes3D
# from mpl_toolkits.mplot3d.art3d import Line3DCollection
# import matplotlib.animation as ani

sys.path.append('./Calib') #NEED TO POINT THIS TO THE Calib MODULE FOLDER!!!
from calib import traj_opt
from .app import triangulate_points_fisheye
from .utils import create_board_object_pts, \
    load_scene, \
    load_points, \
    load_defined_points

def create_camera(color=(0.1, 0.1, 0.1, 1)):
    ## plot camera
    bx = 0.15
    by = 0.1
    bz = 0.1
    m = max([bx, by, bz])
    verts = np.array([
        [bx, by, bz],
        [bx, by, -bz],
        [bx, -by, bz],
        [bx, -by, -bz],
        [-bx, by, bz],
        [-bx, by, -bz],
        [-bx, -by, bz],
        [-bx, -by, -bz],
        [2 * bx, 2 * by, 2 * bz],
        [2 * bx, -2 * by, 2 * bz],
        [-2 * bx, 2 * by, 2 * bz],
        [-2 * bx, -2 * by, 2 * bz],
        [0, 0, 0],
        [5*m, 0, 0],
        [0, 5*m, 0],
        [0, 0, 5*m]
    ])
    edges = np.array([
        [0,1],
        [0,2],
        [0,4],
        [1,3],
        [1,5],
        [2,3],
        [2,6],
        [3,7],
        [4,5],
        [4,6],
        [5,7],
        [6,7],
        [0,8],
        [2,9],
        [4,10],
        [6,11],
        [8,9],
        [8,10],
        [9,11],
        [10,11],
        [12,13],
        [12,14],
        [12,15]
    ]).flatten()
    colors = np.array([color for _ in range(len(edges))])
    colors[[40,41]] = (1., 0., 0., 1)
    colors[[42,43]] = (0., 1., 0., 1)
    colors[[44,45]] = (0., 0., 1., 1)

    mesh = gl.GLLinePlotItem(pos=verts[edges], color=colors, width=1.0, antialias=True, mode='lines')
    return mesh


def create_grid(obj_points, board_shape, color=(0.5, 0.5, 0.5, 1)):
    cols = board_shape[0]
    rows = board_shape[1]
    xyz_quiver = np.array([
        [0, 0, 0],
        [0.1, 0, 0],
        [0, 0.1, 0],
        [0, 0, 0.1]
    ])
    verts = np.vstack([obj_points, xyz_quiver])

    edges = []
    for r in range(rows):
        for c in range(cols-1):
            edges.append(c+r*cols)
            edges.append(c+r*cols+1)
    for c in range(cols):
        for r in range(rows-1):
            edges.append(c+r*cols)
            edges.append(c+(r+1)*cols)
    edges.extend(np.array([0,1,0,2,0,3])+(rows*cols))

    colors = np.array([color for _ in range(len(edges))])
    colors[[-6,-5]] = (1, 0, 0, 1)
    colors[[-4,-3]] = (0, 1, 0, 1)
    colors[[-2,-1]] = (0, 0, 1, 1)

    mesh = gl.GLLinePlotItem(pos=verts[edges], color=colors, width=1.0, antialias=True, mode='lines')
    return mesh


def plot_calib_board(img_points, board_shape, camera_resolution, frame_fpath=None):
    from IPython.display import clear_output
    
    corners = np.array(img_points, dtype=np.float32)
    plt.figure(figsize=(8, 4.5))
    if frame_fpath:
        plt.imshow(plt.imread(frame_fpath))

    for pts in corners:
        pts = pts.reshape(-1, 2)
        cols = board_shape[0]
        rows = board_shape[1]
        edges = []
        for r in range(rows):
            for c in range(cols - 1):
                edges.append(c + r * cols)
                edges.append(c + r * cols + 1)
        for c in range(cols):
            for r in range(rows - 1):
                edges.append(c + r * cols)
                edges.append(c + (r + 1) * cols)
        lc = mc.LineCollection(pts[edges].reshape(-1, 2, 2), color='r', linewidths=0.25)

        plt.gca().add_collection(lc)
        plt.gca().set_xlim((0, camera_resolution[0]))
        plt.gca().set_ylim((camera_resolution[1], 0))
    
    plt.show()

class Animation:
    def __init__(self):
        self.app = QApplication.instance()
        if self.app == None:
            self.app = QApplication([])
            
        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor("#FFFFFF")
        
        # Grid
        grid = gl.GLGridItem(size=QtGui.QVector3D(50,50,1), color=(200,200,200,255))
        grid.setGLOptions('translucent')
        self.view.addItem(grid)
        
    def rodrigues_to_vec(self, r):
        ang = 180 / np.pi * np.linalg.norm(r)
        return (ang, *r)

    def plot_camera(self, r, t):
        # Uses camera pose!
        # Note: T is the world origin position in the camera coordinates
        #       the world position of the camera C = -(R^-1)@T.
        #       Similarly, the rotation of the camera in world coordinates
        #       is given by R^-1.
        #       The inverse of a rotation matrix is also its transpose.
        # https://en.wikipedia.org/wiki/Camera_resectioning#Extrinsic_parameters
        R = r.T
        T = -r.T@t
        # Convert for plotting
        R = cv2.Rodrigues(R)[0]
        R = self.rodrigues_to_vec(R)
        cam = create_camera()
        cam.rotate(*R)
        cam.translate(*T)
        self.view.addItem(cam)
    
    
class Scene(Animation):
    def __init__(self):
        Animation.__init__(self)
        self.view.opts['distance']=13
        self.view.pan(2.5,5,0)
        self.view.orbit(-120,10)
        self.view.update()
        self.view.show()

    def plot_calib_board(self, r, t, board_shape, board_edge_len):
        obj_pts = create_board_object_pts(board_shape, board_edge_len)
        calib_board = create_grid(obj_pts, board_shape)
        calib_board.translate(*t)
        r = self.rodrigues_to_vec(r)
        calib_board.rotate(*r)
        self.view.addItem(calib_board)

    def plot_points(self, points, color=(0,0.5,0.5,0.5), size=3):
        scatter = gl.GLScatterPlotItem(pos=points, color=color, size=size, pxMode=True)
        scatter.setGLOptions('translucent')
        self.view.addItem(scatter)

    def show(self):
        self.app.exec_()

    def save(self, filename, size=(800, 450)):
        pyqtgraph.makeQImage(self.view.renderToArray(size)).save(filename)
        self.app.quit()

        
def plot_scene(scene_fpath, points_fpaths, cam_pairs=None, plot_defined_pts=False):
    
    k_arr, d_arr, r_arr, t_arr, _ = load_scene(scene_fpath)
    n_cams = len(k_arr)

    def _get_corresponding_image_points(pts_1, names_1, pts_2, names_2):
        names = []
        img_pts_1 = []
        img_pts_2 = []
        for i, (p1, n1) in enumerate(zip(pts_1, names_1)):
            for j, (p2, n2) in enumerate(zip(pts_2, names_2)):
                if n1 == n2:
                    names.append(n1)
                    img_pts_1.append(p1)
                    img_pts_2.append(p2)
        img_pts_1 = np.array(img_pts_1)
        img_pts_2 = np.array(img_pts_2)
        return img_pts_1, img_pts_2, names

    scene = Scene()  # the error happans here
    for r, t in zip(r_arr, t_arr):
        scene.plot_camera(r, t)
    colors = [
        (1,0,0,0.99),     # red: cam pair 0&1
        (0,1,0,0.99),     # greeen: cam pair 1&2
        (0,0,0,0.99),     # black: cam pair 2&3
        (0,0,1,0.99),     # blue: cam pair 3&4
        (0,0.8,0.8,0.99), # light blue: cam pair 4&5
        (1,0,1,0.99)      # fuchsia/magenta: cam pair 5&0
    ]
    
    if plot_defined_pts:
        pts_2d, *_ = load_defined_points(points_fpaths)
        
        # If cam pairs are not specified, plot all available cam pairs
        if cam_pairs is None:
            cam_pairs = []
            for cam in range(n_cams):
                cam_pairs.append(sorted([cam%n_cams, (cam+1)%n_cams]))
        
        for i in cam_pairs:
            try:
                img_pts_1 = np.array(pts_2d[:, i[0]])
                img_pts_2 = np.array(pts_2d[:, i[1]])
                
                pts_3d = triangulate_points_fisheye(
                    img_pts_1, img_pts_2, 
                    k_arr[i[0]], d_arr[i[0]], r_arr[i[0]], t_arr[i[0]],
                    k_arr[i[1]], d_arr[i[1]], r_arr[i[1]], t_arr[i[1]]
                )
                scene.plot_points(pts_3d, color=colors[cam_pairs.index(i)], size=10)
            except:
                pass
    else:
        for cam in range(n_cams):
            i, j = sorted([cam%n_cams, (cam+1)%n_cams])
            pts_1, names_1, *_ = load_points(points_fpaths[i])
            pts_2, names_2, *_ = load_points(points_fpaths[j])
            try:
                img_pts_1, img_pts_2, _ = _get_corresponding_image_points(
                    pts_1, names_1,
                    pts_2, names_2
                )
                pts_3d = triangulate_points_fisheye(
                    img_pts_1, img_pts_2, 
                    k_arr[i], d_arr[i], r_arr[i], t_arr[i],
                    k_arr[j], d_arr[j], r_arr[j], t_arr[j]
                )
                scene.plot_points(pts_3d, color=colors[cam])
            except:
                pass
    
    scene.show()
    
def plot_checkerboard_pts(scene_fpath, points_fpaths):
    plot_scene(scene_fpath, points_fpaths)

def plot_all_defined_pts(scene_fpath, defined_points_fpath):
    plot_scene(scene_fpath, defined_points_fpath, plot_defined_pts=True)
    
def plot_defined_pts_certain_pairs(scene_fpath, defined_points_fpath, cam_pairs):
    plot_scene(scene_fpath, defined_points_fpath, cam_pairs, plot_defined_pts=True)
    
    
class Cheetah(Animation):
    def __init__(self, scatter_frames, lines_frames, K_arr,D_arr,R_arr,t_arr):
        Animation.__init__(self)
        self.view.opts['distance']=30
        self.scatter_frames = np.array(scatter_frames)
        self.lines_frames = np.array(lines_frames)
        self.n_frames = len(scatter_frames)
        self.frame = 0
        self.n_cams = len(K_arr)
        
        self.K_arr = K_arr
        self.D_arr = D_arr
        self.R_arr = R_arr
        self.t_arr = t_arr
        
        self.win = pyqtgraph.GraphicsWindow(title="Cheetah")
        self.layout = QGridLayout()
        self.win.setLayout(self.layout)
        self.win.setBackground((255, 255, 255))
        
        # ====== 3D ======
        self.view.sizeHint = lambda: pyqtgraph.QtCore.QSize(1280, 720)
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.view, 0, 0, self.n_cams, 1)
        
        #create dots
        self.scatter = gl.GLScatterPlotItem(pos=self.scatter_frames[0], color=[1,0,0,1], size=0.05, pxMode=False)
        self.scatter.setGLOptions('translucent')
        self.view.addItem(self.scatter)
        
        #create links
        self.lines = gl.GLLinePlotItem(pos=self.lines_frames[0], color=[0,0,0,1], width=1.5, antialias=True, mode='lines')
        self.lines.setGLOptions('translucent')
        self.view.addItem(self.lines)
        
        for r, t in zip(self.R_arr, self.t_arr):
            self.plot_camera(r, t)
        
        # ====== 2D ======
        self.cam_w = []
        self.cam_data = []
        self.cam_scatter = []
        self.cam_lines = []
        for i in range(self.n_cams):
            self.cam_w.append(pyqtgraph.PlotWidget(color=(0,0,0,1.0)))
            self.cam_data.append(pyqtgraph.PlotDataItem(connect="pairs"))
            self.cam_w[i].getPlotItem().addItem(self.cam_data[i])
            self.cam_w[i].getPlotItem().setXRange(0, 2704)
            self.cam_w[i].getPlotItem().setYRange(1520, 0)
            self.cam_w[i].getPlotItem().invertY()
            
            self.cam_w[i].sizeHint = lambda: pyqtgraph.QtCore.QSize(256, 144)
            self.cam_w[i].setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.cam_w[i].setBackground((255,255,255))
            
            self.layout.addWidget(self.cam_w[i], i, 1, 1, 1)
            cam_lines_temp = []
            for j in range(self.n_frames):
                lines_frames_2d = [traj_opt.pt3d_to_2d(*pt, self.K_arr[i], self.D_arr[i], self.R_arr[i], self.t_arr[i])for pt in self.lines_frames[j]]
                cam_lines_temp.append(lines_frames_2d)
            self.cam_lines.append(np.array(cam_lines_temp))
            self.cam_data[i].setData(self.cam_lines[i][0])

    def start(self):
        if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
            QApplication.instance().exec_()

    def update(self):
        self.scatter.setData(pos=self.scatter_frames[self.frame])
        self.lines.setData(pos=self.lines_frames[self.frame])
        self.frame = (self.frame+1)%self.n_frames
        for i in range(self.n_cams):
            self.cam_data[i].setData(self.cam_lines[i][self.frame])

    def animation(self):
        timer = QtCore.QTimer()
        timer.timeout.connect(self.update)
        timer.start(100)
        self.start()
        
    def plot(self, frames):
        self.scatter.setData(pos=self.scatter_frames[frames].reshape(-1, 3))
        self.lines.setData(pos=self.lines_frames[frames].reshape(-1, 3))
        for i in range(self.n_cams):
            self.cam_data[i].setData(self.cam_lines[i][frames].reshape(-1, 2))
        self.start()
        

# def plot_cheetah_graphs(plot_style_fpath, lure_pts, x_opt):
def plot_cheetah_graphs(plot_style_fpath, x_opt):
    plt.style.use(plot_style_fpath)
    fig, axs = plt.subplots(8, 2, figsize=(13,30))
    
#     axs[0,0].plot(lure_pts)
#     axs[0,0].set_title("Lure positions")
#     axs[0,0].legend(['x', 'y', 'z'])
    
    axs[0,1].plot(x_opt[:, [0,1,2]])
    axs[0,1].set_title("Head positions")
    axs[0,1].legend(['x0', 'y0', 'z0'])

    axs[1,0].plot(x_opt[:, [3,17,31]])
    axs[1,0].set_title("Head angles")
    axs[1,0].legend(['phi0', 'theta0', 'psi0'])

    axs[1,1].plot(x_opt[:, [4,18,32]])
    axs[1,1].set_title("Neck angles")
    axs[1,1].legend(['phi1', 'theta1', 'psi1'])

    axs[2,0].plot(x_opt[:, [19]])
    axs[2,0].set_title("Front torso angles")
    axs[2,0].legend(['theta2'])

    axs[2,1].plot(x_opt[:, [6,20,34]])
    axs[2,1].set_title("Back torso angles")
    axs[2,1].legend(['phi3','theta3', 'psi3'])

    axs[3,0].plot(x_opt[:, [21,35]])
    axs[3,0].set_title("Tail base")
    axs[3,0].legend(['theta4', 'psi4'])

    axs[3,1].plot(x_opt[:, [22,36]])
    axs[3,1].set_title("Tail Mid")
    axs[3,1].legend(['theta5', 'psi5'])

    axs[4,0].plot(x_opt[:, [23]])
    axs[4,0].set_title("Left shoulder angles")
    axs[4,0].legend(['theta6'])

    axs[4,1].plot(x_opt[:, [24]])
    axs[4,1].set_title("Left front knee angle")
    axs[4,1].legend(['theta7'])

    axs[5,0].plot(x_opt[:, [25]])
    axs[5,0].set_title("Right shoulder angles")
    axs[5,0].legend(['theta8'])

    axs[5,1].plot(x_opt[:, [26]])
    axs[5,1].set_title("Right front knee angle")
    axs[5,1].legend(['theta9'])

    axs[6,0].plot(x_opt[:, [27]])
    axs[6,0].set_title("Left hip angle")
    axs[6,0].legend(['theta10'])

    axs[6,1].plot(x_opt[:, [28]])
    axs[6,1].set_title("Left back knee angle")
    axs[6,1].legend(['theta11'])

    axs[7,0].plot(x_opt[:, [29]])
    axs[7,0].set_title("Right hip angle")
    axs[7,0].legend(['theta12'])

    axs[7,1].plot(x_opt[:, [30]])
    axs[7,1].set_title("Right back knee angle")
    axs[7,1].legend(['theta13'])
    
    fig.savefig(os.path.join(DATA_DIR, 'figure.pdf'))
    return fig, axs