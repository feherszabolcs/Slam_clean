from multiprocessing import Process, Queue
import numpy as np
import cv2
import pypangolin
import OpenGL.GL as gl

# Global map // 3D map visualization using pypangolin
class Map(object):
    def __init__(self):
        self.frames = [] # camera frames [means camera pose]
        self.points = [] # 3D points of map
        self.state = None # variable to hold current state of the map and cam pose
        self.q = None # A queue for inter-process communication. | q for visualization process
        self.q_image = None
        self.inliers = None
        self.plane = None
        
    def create_viewer(self):
        # Parallel Execution: The main purpose of creating this process is to run 
        # the `viewer_thread` method in parallel with the main program. 
        # This allows the 3D viewer to update and render frames continuously 
        # without blocking the main execution flow.
        
        self.q = Queue() # q is initialized as a Queue
        self.q_image = Queue()

        # initializes the Parallel process with the `viewer_thread` function 
        # the arguments that the function takes is mentioned in the args var
        p = Process(target=self.viewer_thread, args=(self.q,)) 
        
        # daemon true means, exit when main program stops
        p.daemon = True
        
        # starts the process
        p.start()

    def viewer_thread(self, q):
        # `viewer_thread` takes the q as input
        # initializes the viz window
        self.viewer_init(1280, 720)
        # An infinite loop that continually refreshes the viewer
        while True:
            self.viewer_refresh(q)

    def viewer_init(self, w, h):
        pypangolin.CreateWindowAndBind('Main', w, h)
        
        # This ensures that only the nearest objects are rendered, 
        # creating a realistic representation of the scene with 
        # correct occlusions.
        gl.glEnable(gl.GL_DEPTH_TEST)

        # Sets up the camera with a projection matrix and a model-view matrix
        self.scam = pypangolin.OpenGlRenderState(
            # `ProjectionMatrix` The parameters specify the width and height of the viewport (w, h), the focal lengths in the x and y directions (420, 420), the principal point coordinates (w//2, h//2), and the near and far clipping planes (0.2, 10000). The focal lengths determine the field of view, 
            # the principal point indicates the center of the projection, and the clipping planes define the range of distances from the camera within which objects are rendered, with objects closer than 0.2 units or farther than 10000 units being clipped out of the scene. 
            pypangolin.ProjectionMatrix(w, h, 420, 420, w//2, h//2, 0.2, 10000),
            # pypangolin.ModelViewLookAt(0, -10, -8, 0, 0, 0, 0, -1, 0) sets up the camera view matrix, which defines the position and orientation of the camera in the 3D scene. The first three parameters (0, -10, -8) specify the position of the camera in the world coordinates, indicating that the camera is located at coordinates (0, -10, -8). The next three parameters (0, 0, 0) 
            # define the point in space the camera is looking at, which is the origin in this case. The last three parameters (0, -1, 0) represent the up direction vector, indicating which direction is considered 'up' for the camera, here pointing along the negative y-axis. This setup effectively positions the camera 10 units down and 8 units back from the origin, looking towards the origin with the 'up' direction being downwards in the y-axis, which is unconventional and might be used to achieve a specific orientation or perspective in the rendered scene.
            pypangolin.ModelViewLookAt(0, -10, -8, 0, 0, 0, 0, -1, 0))
        # Creates a handler for 3D interaction.
        self.handler = pypangolin.Handler3D(self.scam)
        

 
        # Creates a display context.
        self.dcam = pypangolin.CreateDisplay()
        # Sets the bounds of the display
        self.dcam.SetBounds(pypangolin.Attach(0.0), pypangolin.Attach(1.0), pypangolin.Attach(0.0), pypangolin.Attach(1.0), -w/h)
        # assigns handler for mouse clicking and stuff, interactive
        self.dcam.SetHandler(self.handler)
        # self.darr = None

        # image
        width, height = 480, 270
        self.dimg = pypangolin.Display('image')
        self.dimg.SetBounds(pypangolin.Attach(0), pypangolin.Attach(height / 768.),pypangolin.Attach(0.0), pypangolin.Attach(width / 1024.), 1024 / 768.)
        #self.dimg.SetLock(pypangolin.Lock.LockLeft, pypangolin.Lock.LockTop)
        self.texture = pypangolin.GlTexture(width, height, gl.GL_RGB, False, 0, gl.GL_RGB, gl.GL_UNSIGNED_BYTE)
        self.image = np.ones((height, width, 3), 'uint8')



    def viewer_refresh(self, q):
        width, height = 480, 270

        # Checks if the current state is None or if the queue is not empty.
        if self.state is None or not q.empty():
            # Gets the latest state from the queue.
            self.state = q.get()
        
        # Clears the color and depth buffers.
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        # Sets the clear color to white.
        gl.glClearColor(1.0, 1.0, 1.0, 1.0)
        # Activates the display context with the current camera settings.
        self.dcam.Activate(self.scam)

        # camera trajectory line and color setup
        gl.glLineWidth(1)
        gl.glColor3f(0.0, 1.0, 0.0)
        #pypangolin.DrawCameras(self.state[0])
        gl.glBegin(gl.GL_LINE_STRIP)
        for camera in self.state[0]:
            gl.glVertex3f(camera[0, 3], camera[1, 3], camera[2, 3])
        gl.glEnd()

        # 3d point cloud color setup
        gl.glPointSize(2)
        gl.glColor3f(1.0, 0.0, 0.0)
        #pypangolin.DrawPoints(self.state[1])
        gl.glBegin(gl.GL_POINTS)
        for point in self.state[1]:
            gl.glVertex3f(point[0], point[1], point[2])
        gl.glEnd()
        
        if self.state[2] is not None:
            gl.glPointSize(4)
            gl.glColor3f(0.0, 1.0, 0.0)
            gl.glBegin(gl.GL_POINTS)
            for idx in self.state[2]:
                point = self.state[1][idx]
                gl.glVertex3f(point[0], point[1], point[2])
            gl.glEnd()

        if hasattr(self, 'plane') and self.plane is not None:
            normal = self.plane[:3]
            d = self.plane[3]
            gl.glPointSize(1)
            gl.glColor3f(1.0, 1.0, 0.0)
            gl.glBegin(gl.GL_POINTS)
            for x in range(-10, 10):
                for y in range(-10, 10):
                    z = (-d - normal[0] * x - normal[1] * y) / normal[2]
                    gl.glVertex3f(x, y, z)
            gl.glEnd()
        
        # show image
        if not self.q_image.empty():
            self.image = self.q_image.get()
            if self.image.ndim == 3:
                self.image = self.image[::-1, :, ::-1]
            else:
                self.image = np.repeat(self.image[::-1, :, np.newaxis], 3, axis=2)
            self.image = cv2.resize(self.image, (width, height))
        if True:         
            self.texture.Upload(self.image, gl.GL_RGB, gl.GL_UNSIGNED_BYTE)
            self.dimg.Activate()
            gl.glColor3f(1.0, 1.0, 1.0)
            self.texture.RenderToViewport()

        # Finishes the current frame and swaps the buffers.
        pypangolin.FinishFrame()
    
    def remove_radius_outliers(self, radius=1.0, min_neighbors=2):
        """Remove points that have fewer than min_neighbors within a given radius"""
        if len(self.points) < 50:  # Only run when we have enough points
            return
        
        # Extract all point positions
        positions = np.array([point.pt[:3] for point in self.points])
        
        # Calculate the number of neighbors within the radius for each point
        neighbors_count = np.zeros(len(self.points), dtype=int)
        for i, pos in enumerate(positions):
            distances = np.linalg.norm(positions - pos, axis=1)
            neighbors_count[i] = np.sum(distances < radius) - 1  # Exclude self-distance
        
        # Identify outliers
        outlier_indices = np.where(neighbors_count < min_neighbors)[0]
        
        # Remove outliers (in reverse order to avoid index issues)
        for idx in sorted(outlier_indices, reverse=True):
            self.points.pop(idx)

    def downsample(self, voxel_size=0.1):
        """Downsample the point cloud using a voxel grid filter"""
        if len(self.points) < 50:  # Only run when we have enough points
            return
        
        # Extract all point positions
        positions = np.array([point.pt[:3] for point in self.points])
        
        # Compute voxel indices for each point
        voxel_indices = np.floor(positions / voxel_size).astype(np.int32)
        
        # Use a dictionary to keep only one point per voxel
        voxel_dict = {}
        for idx, voxel_index in enumerate(voxel_indices):
            voxel_key = tuple(voxel_index)
            if voxel_key not in voxel_dict:
                voxel_dict[voxel_key] = idx
        
        # Create a new list of points with only one point per voxel
        downsampled_points = [self.points[idx] for idx in voxel_dict.values()]
        
        # Replace the original points with the downsampled points
        self.points = downsampled_points    

    def filter_by_reprojection_error(self,K, error_threshold=2.0):
        """Remove points with high reprojection error"""
        
        if len(self.points) < 10:
            return
        
        points_to_remove = []
        
        for point in self.points:
            total_error = 0
            observations = 0
            
            for frame, idx in zip(point.frames, point.idxs):
                # Project 3D point to 2D
                proj = np.dot(frame.pose, np.append(point.pt[:3], 1))
                if(proj[2] <= 0):
                    continue
                proj = proj[:3] / proj[2]
                proj_2d = np.dot(K, proj)
                proj_2d = proj_2d[:2]
                
                # Get the original 2D point
                orig_2d = frame.pts[idx]
                
                # Calculate reprojection error
                error = np.linalg.norm(proj_2d - orig_2d)
                total_error += error
                observations += 1
            
            if observations > 2 and (total_error / observations) > error_threshold:
                points_to_remove.append(point)
        
        # Remove points with high reprojection error
        max_remove = min(len(points_to_remove), len(self.points) // 10)
        if max_remove > 0:
            for point in points_to_remove[:max_remove]:
                if point in self.points:
                    self.points.remove(point)

    def optimize(self):
        """Simple bundle adjustment to refine point positions and camera poses"""
        if len(self.points) < 10 or len(self.frames) < 3:
            return
            
        # Collect observations
        observations = []
        point_indices = []
        camera_indices = []
        
        for i, point in enumerate(self.points):
            for j, (frame, idx) in enumerate(zip(point.frames, point.idxs)):
                observations.append(frame.pts[idx])
                point_indices.append(i)
                camera_indices.append(self.frames.index(frame))
        
        # Convert to numpy arrays
        observations = np.array(observations)
        point_indices = np.array(point_indices)
        camera_indices = np.array(camera_indices)


    def display(self):
        if self.q is None:
            return
        poses, pts = [], []
        for f in self.frames:
            # updating pose
            poses.append(f.pose)

        for p in self.points:
            # updating map points
            pts.append(p.pt)
        
        # updating queue
        self.q.put((np.array(poses), np.array(pts), self.inliers, self.plane))

    def display_image(self, ip_image):
        # if self.q is None:
        #     return
        self.q_image.put(ip_image)


class Point(object):
    # A Point is a 3-D point in the world
    # Each point is observed in multiple frames

    def __init__(self, mapp, loc):
        self.frames = []
        self.pt = loc
        self.idxs = []

        # assigns a unique ID to the point based on the current number of points in the map.
        self.id = len(mapp.points)
        # adds the point instance to the map’s list of points.
        mapp.points.append(self)

    def add_observation(self, frame, idx):
        # Frame is the frame class
        self.frames.append(frame)
        self.idxs.append(idx)

