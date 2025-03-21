import cv2
import glob
from display import Display
from extractor import Frame, denormalize, match_frames, add_ones
import numpy as np
import random
from pointmap import Map, Point
from utils import read_calibration_file, extract_intrinsic_matrix

# calib_file_path = "../data/data_odometry_gray/dataset/sequences/00/calib.txt"
# calib_lines = read_calibration_file(calib_file_path)
# K = extract_intrinsic_matrix(calib_lines, camera_id='P0')

# Camera intrinsics
W, H = 1920//2,  1080//2
# F = 270
F = 450
K = np.array([[F, 0, W // 2], [0, F, H // 2], [0, 0, 1]])


Kinv = np.linalg.inv(K)

#display = Display(1280, 720)
mapp = Map()
mapp.create_viewer()

def triangulate(pose1, pose2, pts1, pts2):
    ret = np.zeros((pts1.shape[0], 4))
    pose1 = np.linalg.inv(pose1)
    pose2 = np.linalg.inv(pose2)
    for i, p in enumerate(zip(add_ones(pts1), add_ones(pts2))):
        A = np.zeros((4, 4))
        A[0] = p[0][0] * pose1[2] - pose1[0]
        A[1] = p[0][1] * pose1[2] - pose1[1]
        A[2] = p[1][0] * pose2[2] - pose2[0]
        A[3] = p[1][1] * pose2[2] - pose2[1]
        _, _, vt = np.linalg.svd(A)
        ret[i] = vt[3]

    return ret

frame_counter = 0

def ransac_plane_fitting(points, threshold=0.1, max_iterations=1000):
    best_plane = None
    best_inliers = []

    for _ in range(max_iterations):
        # Randomly sample 3 points
        sample_indices = random.sample(range(points.shape[0]), 3)
        sample_points = points[sample_indices]

        # Fit a plane to these 3 points
        p1, p2, p3 = sample_points
        normal = np.cross(p2 - p1, p3 - p1)
        normal = normal / np.linalg.norm(normal)
        d = -np.dot(normal, p1)
        plane = np.append(normal, d)

        # Calculate distances of all points to the plane
        distances = np.abs(np.dot(points, normal) + d)

        # Identify inliers
        inliers = np.where(distances < threshold)[0]

        # Update the best plane if this one has more inliers
        if len(inliers) > len(best_inliers):
            best_plane = plane
            best_inliers = inliers

    return best_plane, best_inliers

def process_frame(img):
    
    global frame_counter
    frame_counter += 1

    if frame_counter % 1 != 0:
        return
    

    img = cv2.resize(img, (W, H))
    frame = Frame(mapp, img, K)
    if frame.id == 0:
        return

    # previous frame f2 to the current frame f1.
    f1 = mapp.frames[-1]
    f2 = mapp.frames[-2]

    
    
    idx1, idx2, Rt = match_frames(f1, f2)
    print(f"=------------Rt {Rt}")
    # f2.pose represents the transformation from the world coordinate system to the coordinate system of the previous frame f2.
    # Rt represents the transformation from the coordinate system of f2 to the coordinate system of f1.
    # By multiplying Rt with f2.pose, you get a new transformation that directly maps the world coordinate system to the coordinate system of f1.
    f1.pose = np.dot(Rt, f2.pose)


    # The output is a matrix where each row is a 3D point in homogeneous coordinates [𝑋, 𝑌, 𝑍, 𝑊]
    pts4d = triangulate(f1.pose, f2.pose, f1.pts[idx1], f2.pts[idx2])
    
    # This line normalizes the 3D points by dividing each row by its fourth coordinate W
    # The homogeneous coordinates [𝑋, 𝑌, 𝑍, 𝑊] are converted to Euclidean coordinates
    pts4d /= pts4d[:, 3:]

    good_pts4d = (np.abs(pts4d[:, 3]) > 0.001) #  & (pts4d[:, 2] > 0)
    
    latest_cam_pos = f1.pose[:3, 3]
    distance_from_camera = np.linalg.norm(pts4d[:, :3] - latest_cam_pos, axis=1)
    good_pts4d = good_pts4d & (distance_from_camera < 20)

    for i, p in enumerate(pts4d):
        #  If the point is not good (i.e., good_pts4d[i] is False), the loop skips the current iteration and moves to the next point.
        if not good_pts4d[i]:
            continue
        pt = Point(mapp, p)
        pt.add_observation(f1, idx1[i])
        pt.add_observation(f2, idx2[i])
    
    if frame_counter % 5 == 0 and len(mapp.frames) >= 3:
        mapp.optimize() 

    if(frame_counter % 10 == 0 and len(mapp.points) > 50):
        mapp.filter_by_reprojection_error(K,3.0)
        # mapp.remove_radius_outliers(radius=1.0, min_neighbors=2)
        mapp.downsample(voxel_size=0.1)

    points = np.array([point.pt[:3] for point in mapp.points])
    # points = pre_filter_points(points)


    plane, inliers = ransac_plane_fitting(points)

    mapp.inliers = inliers
    mapp.plane = plane

    print(f"RANSAC plane: {plane}")
    print(f"Number of inliers: {len(inliers)}")

    road_points = points[inliers]
    non_road_points = np.delete(points, inliers, axis=0)

    for pt in road_points:
        u, v = denormalize(K, pt[:2])
        cv2.circle(img, (u, v), 2, (0, 255, 0), -1)  # Green for inliers

    # Visualize the non-road points (outliers)
    for pt in non_road_points:
        u, v = denormalize(K, pt[:2])
        cv2.circle(img, (u, v), 2, (0, 0, 255), -1)  # Red for outliers

    # Draw the plane (optional)
    if plane is not None:
        normal = plane[:3]
        d = plane[3]
        # Draw the plane as a grid of points
        for x in range(-10, 10):
            for y in range(-10, 10):
                z = (-d - normal[0] * x - normal[1] * y) / normal[2]
                pt = np.array([x, y, z])
                u, v = denormalize(K, pt[:2])
                cv2.circle(img, (u, v), 1, (255, 255, 0), -1)  # Yellow for plane points

    for pt1, pt2 in zip(f1.pts[idx1], f2.pts[idx2]):
        u1, v1 = denormalize(K, pt1)
        u2, v2 = denormalize(K, pt2)

        cv2.circle(img, (u1,v1), 2, (77, 243, 255))

        cv2.line(img, (u1,v1), (u2, v2), (255,0,0))
        cv2.circle(img, (u2, v2), 2, (204, 77, 255))
    
    
    # 2-D display
    #img = cv2.resize(img, ( 320, 180))
    #display.paint(img)

    # 3-D display
    mapp.display()
    mapp.display_image(img)


if __name__== "__main__":
    cap = cv2.VideoCapture("car.mp4") 

    while cap.isOpened():
        ret, frame = cap.read()
        #print("frame shape: ", frame.shape)
        print("\n#################  [NEW FRAME]  #################\n")
        if ret == True:
            process_frame(frame)
        else:
            break
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # Release the capture and close any OpenCV windows
    cap.release()
    cv2.destroyAllWindows()