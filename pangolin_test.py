import OpenGL.GL as gl
import pypangolin
import numpy as np

def main():
    pypangolin.CreateWindowAndBind('Main', 640, 480)
    gl.glEnable(gl.GL_DEPTH_TEST)

    # Define Projection and initial ModelView matrix
    scam = pypangolin.OpenGlRenderState(
        pypangolin.ProjectionMatrix(640, 480, 420, 420, 320, 240, 0.2, 100),
        pypangolin.ModelViewLookAt(-2, 2, -2, 0, 0, 0, pypangolin.AxisDirection.AxisY))
    handler = pypangolin.Handler3D(scam)

    # Create Interactive View in window
    dcam = pypangolin.CreateDisplay()
    dcam.SetBounds(
        pypangolin.Attach(0.0), 
        pypangolin.Attach(1.0), 
        pypangolin.Attach(0.0), 
        pypangolin.Attach(1.0), 
        -640.0 / 480.0)
    dcam.SetHandler(handler)

    while not pypangolin.ShouldQuit():
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glClearColor(1.0, 1.0, 1.0, 1.0)
        dcam.Activate(scam)
        
        # Render OpenGL Cube
        pypangolin.glDrawColouredCube()

        # Draw Point Cloud
        points = np.random.random((100000, 3)) * 10
        colors = np.zeros((len(points), 3))
        colors[:, 1] = 1 -points[:, 0] / 10.
        colors[:, 2] = 1 - points[:, 1] / 10.
        colors[:, 0] = 1 - points[:, 2] / 10.

        gl.glPointSize(2)
        gl.glBegin(gl.GL_POINTS)
        for i in range(len(points)):
            gl.glColor3f(colors[i, 0], colors[i, 1], colors[i, 2])
            gl.glVertex3f(points[i, 0], points[i, 1], points[i, 2])
        gl.glEnd()
        #gl.glColor3f(1.0, 0.0, 0.0)
        # access numpy array directly(without copying data), array should be contiguous.
        #pypangolin.DrawPoints(points, colors)    

        pypangolin.FinishFrame()



if __name__ == '__main__':
    main()