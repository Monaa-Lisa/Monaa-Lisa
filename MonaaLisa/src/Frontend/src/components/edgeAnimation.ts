/* edgeAnimation.ts
14- February-2025 - nick - edge network animation
Manages animated edges between clusters for category views.
dynamic, randomized edge animation system with Bézier curves
connecting random points within clusters, with individual lifetimes and directions.
draws random edges between clusters in category views, with individual lifetimes and directions
Purely cosmetic, serves no actual purpose other than visual chaos and interest
*/

import type { ClusterNode } from '$lib/types/paper';

/*
 represents a cluster with layout information for visualization.
 Extends the base ClusterNode with additional properties needed for rendering and animation
*/
interface LayoutCluster extends ClusterNode {
  x: number;
  y: number;
  //radius of the clusters area, used for the particle distribution and point generation
  radius: number;
  color: string;
}

/*
 Transform object for converting world coordinates to screen coordinates
 Used to map the abstract world space (where the clusters are positioned currently) 
 to the actual pixel coordinates on the canvas.
 this is so zooming, panning etc. works
*/
interface Transform {
  //scaling factor to zoom in/out of the world space
  scale: number;
  //horizontal offset to pan the view left and right
  offsetX: number;
  //vertical offset to pan the view up anddown 
  offsetY: number;
}

/*
 the animated edge between two clusters
*/
interface AnimatedEdge {
  //The starting cluster
  startCluster: LayoutCluster;
  // The ending cluster
  endCluster: LayoutCluster;
  //random start point within the start cluster
  startPoint: { x: number; y: number };
  // Random end point within the end cluster
  endPoint: { x: number; y: number };
  // timestamp when the edge started animating
  startTime: number;
  // animation progress; 0 to 1 for 'in' phase, 1 to 0 for 'out' phase
  progress: number;
  // animation direction: 
  // 'in' for growing, 'out' for shrinking
  direction: 'in' | 'out';
  // curve direction
  // 1 or -1 for left andright arc 
  curveDirection: number;
  // individual lifetime in ms 
  lifetime: number;
}

/*
manages the animation of edges between clusters in category views.
handles creation, updating, and rendering of randomized bezier curve edges.
 */
export class EdgeAnimator {
  /** array of currently active animated edges. */
  private edges: AnimatedEdge[] = [];
  /** current list of clusters. */
  private clusters: LayoutCluster[] = [];
  /** maximum number of edges to maintain. */
  private maxEdges = 20;
  /** duration of the in/out animation phases in milliseconds. */
  private animationDuration = 2500;

  /*
  initializes the edgeanimator with clusters and pre-populates with random edges.
  @param clusters the array of clusters to animate edges between.
   */
  constructor(clusters: LayoutCluster[]) {
    this.clusters = clusters;
    // initialize with some random edges for immediate visual chaos
    const currentTime = Date.now();
    const initialEdgeCount = Math.floor(Math.random() * 30) + 20; // 20-50 initial edges
    for (let i = 0; i < initialEdgeCount; i++) {
      this.addRandomEdge(currentTime - Math.random() * 12000); // random start in last 12 seconds
    }
  }

  /*
  updates the cluster list and removes edges for non-existent clusters.
  @param clusters the updated array of clusters.
   */
  updateClusters(clusters: LayoutCluster[]) {
    this.clusters = clusters;
    // remove edges where clusters no longer exist
    this.edges = this.edges.filter(edge =>
      this.clusters.some(c => c.id === edge.startCluster.id) &&
      this.clusters.some(c => c.id === edge.endCluster.id)
    );
  }

  /*
  updates the animation state of all edges based on current time.
  handles progress, direction changes, and removal of expired edges.
  @param currentTime the current timestamp in milliseconds.
   */
  update(currentTime: number) {
    // update progress for each edge
    this.edges.forEach(edge => {
      const elapsed = currentTime - edge.startTime; // time elapsed since edge started
      if (edge.direction === 'in') {
        // scale progress from 0 to 1 during animation duration
        edge.progress = Math.min(elapsed / this.animationDuration, 1);
        // switch to 'out' phase when lifetime is near end
        if (elapsed > edge.lifetime - this.animationDuration) {
          edge.direction = 'out';
          edge.startTime = currentTime; // reset start time for out phase
        }
      } else {
        // scale progress from 1 to 0 during animation duration
        edge.progress = 1 - Math.min(elapsed / this.animationDuration, 1);
        // remove edge when fully faded out
        if (edge.progress <= 0) {
          this.edges.splice(this.edges.indexOf(edge), 1);
        }
      }
    });

    // add new edges if below maximum
    while (this.edges.length < this.maxEdges && this.clusters.length >= 2) {
      this.addRandomEdge();
    }
  }

  /*
  adds a new random edge between two different clusters.
  @param startTime optional start time; defaults to current time.
   */
  private addRandomEdge(startTime?: number) {
    const currentTime = startTime ?? Date.now(); // use provided time or current time
    let startIdx: number, endIdx: number;
    // ensure start and end clusters are different to avoid self-loops
    do {
      startIdx = Math.floor(Math.random() * this.clusters.length);
      endIdx = Math.floor(Math.random() * this.clusters.length);
    } while (startIdx === endIdx);

    // select random clusters and generate random points within them
    const startCluster = this.clusters[startIdx];
    const endCluster = this.clusters[endIdx];
    const startPoint = this.randomPointInCluster(startCluster);
    const endPoint = this.randomPointInCluster(endCluster);

    this.edges.push({
      startCluster,
      endCluster,
      startPoint,
      endPoint,
      startTime: currentTime,
      progress: 0,
      direction: 'in',
      curveDirection: Math.random() > 0.5 ? 1 : -1,
      lifetime: 8000 + Math.random() * 4000 // 8-12 seconds
    });
  }

  /*
  renders all active edges on the provided canvas context.
  @param ctx the 2d canvas rendering context.
  @param transform the transformation for world-to-screen coordinates.
   */
  draw(ctx: CanvasRenderingContext2D, transform: Transform) {
    this.edges.forEach(edge => {
      this.drawEdge(ctx, edge, transform);
    });
  }

  /*
  draws a single animated edge as a growing/shrinking bezier curve.
  @param ctx the 2d canvas rendering context.
  @param edge the edge to draw.
  @param transform the transformation for coordinates.
   */
  private drawEdge(ctx: CanvasRenderingContext2D, edge: AnimatedEdge, transform: Transform) {
    // convert world coordinates to screen coordinates
    const start = this.worldToScreen(edge.startPoint.x, edge.startPoint.y, transform);
    const end = this.worldToScreen(edge.endPoint.x, edge.endPoint.y, transform);

    // calculate distance and direction vector
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist === 0) return; // avoid division by zero if points are the same

    // midpoint between start and end
    const midX = (start.x + end.x) / 2;
    const midY = (start.y + end.y) / 2;

    // calculate orthogonal vector for curve direction (left or right arc around clusters)
    const ox = -dy / dist * 150 * edge.curveDirection; // 150 pixels offset
    const oy = dx / dist * 150 * edge.curveDirection;

    // control point for quadratic bezier curve
    const controlX = midX + ox;
    const controlY = midY + oy;

    // draw the curve up to the current progress
    const t = edge.progress;
    ctx.strokeStyle = `rgba(255, 255, 255, ${0.15 * t})`; // semi-transparent white
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);

    // approximate the curve by drawing line segments along the bezier path
    const steps = 50; // number of segments for smoothness
    for (let i = 1; i <= steps; i++) {
      const u = (i / steps) * t; // parameter along the curve up to progress t
      // quadratic bezier formula: b(u) = (1-u)^2 * p0 + 2*(1-u)*u * p1 + u^2 * p2
      const x = (1 - u) * (1 - u) * start.x + 2 * (1 - u) * u * controlX + u * u * end.x;
      const y = (1 - u) * (1 - u) * start.y + 2 * (1 - u) * u * controlY + u * u * end.y;
      ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  /*
  generates a random point within a clusters area.
  @param cluster the cluster to generate a point in.
  @returns a random point within 80% of the clusters radius.
   */
  private randomPointInCluster(cluster: LayoutCluster): { x: number; y: number } {
    // random angle in radians (0 to 2π)
    const angle = Math.random() * 2 * Math.PI;
    // random radius within 80% of cluster radius to stay inside
    const r = Math.random() * cluster.radius * 0.8;
    // calculate point using polar to cartesian conversion
    return {
      x: cluster.x + Math.cos(angle) * r,
      y: cluster.y + Math.sin(angle) * r
    };
  }

  /*
  converts world coordinates to screen coordinates using the transform.
  @param wx world x coordinate.
  @param wy world y coordinate.
  @param t the transform object.
  @returns screen coordinates.
   */
  private worldToScreen(wx: number, wy: number, t: Transform) {
    // apply scaling and translation to convert world coords to screen coords
    return { x: wx * t.scale + t.offsetX, y: wy * t.scale + t.offsetY };
  }
}
