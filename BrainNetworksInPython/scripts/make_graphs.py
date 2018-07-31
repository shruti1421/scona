#!/usr/bin/env python

# A Global import to make code python 2 and 3 compatible
from __future__ import print_function
import numpy as np
import networkx as nx
import pandas as pd


def assign_node_names(G, parcellation, names_308_style=False):
    """
    Returns the network G with node attributes "name" assigned
    according to the list parcellation.

    - G should be a network
    - parcellation should be a list of names where parcellation[i]
     is the name of the ith node of G.

    If you have names in 308 style (as described in Whitaker, Vertes et al
    2016) then you can also add in
        * hemisphere
        * 34_name (Desikan Killiany atlas region)
        * 68_name (Desikan Killiany atlas region with hemisphere)
    """
    # Assign anatomical names to the nodes
    for i, node in enumerate(G.nodes()):
        G.node[node]['name'] = parcellation[i]
        if names_308_style:
            G.node[node]['name_34'] = parcellation[i].split('_')[1]
            G.node[node]['name_68'] = parcellation[i].rsplit('_', 1)[0]
            G.node[node]['hemi'] = parcellation[i].split('_', 1)[0]
    return G


def assign_node_centroids(G, centroids):
    '''
    Assign x,y,z coordinates to each node.

    - G should be a network
    - centroids should be a list of cartesian coordinates where centroids[i]
     is the location of the ith node of G.

    Returns the graph with modified node attributes
    '''
    for i, node in enumerate(G.nodes()):
        G.node[node]['x'] = centroids[i, 0]
        G.node[node]['y'] = centroids[i, 1]
        G.node[node]['z'] = centroids[i, 2]
        G.node[node]['centroids'] = centroids[i, :]
    return G


def weighted_graph_from_matrix(M):
    '''
    Return a networkx weighted graph with edge weights equivalent to matrix
    entries

    M is an adjacency matrix as a numpy array
    '''
    # Make a copy of the matrix
    thr_M = np.copy(M)

    # Set all diagonal values to 0
    thr_M[np.diag_indices_from(thr_M)] = 0

    # Read this full matrix into a graph G
    G = nx.from_numpy_matrix(thr_M)

    return G


def weighted_graph_from_df(df):
    '''
    Return a networkx weighted graph with edge weights equivalent to dataframe
    entries

    M should be an adjacency matrix as a dataframe
    '''
    return weighted_graph_from_matrix(df.values)


def scale_weights(G, scalar=-1, name='weight'):
    '''
    Returns the graph G with the edge weights multiplied by scalar

    G is a networkx graph
    name is the string indexing the edge data
    '''
    edges = nx.get_edge_attributes(G, name=name)
    new_edges = {key: value*scalar for key, value in edges.items()}
    nx.set_edge_attributes(G, name=name, values=new_edges)
    return G


def threshold_graph(G, cost, mst=True):
    '''
    Returns a connected binary graph.

    First creates the minimum spanning tree for the graph, and then adds
    in edges according to their connection strength up to a particular cost.

    G should be a networkx Graph object with edge weights
    cost should be a number between 0 and 100
    '''
    # Weights scaled by -1 as minimum_spanning_tree minimises weight
    H = scale_weights(G.copy())
    # Make a list of all the sorted edges in the full matrix
    H_edges_sorted = sorted(H.edges(data=True),
                            key=lambda edge_info: edge_info[2]['weight'])
    if mst:
        # Calculate minimum spanning tree
        germ = nx.minimum_spanning_tree(H)
    else:
        # Create an empty graph with the same nodes as H
        germ = nx.Graph()
        germ.add_nodes_from(H)

    # Make a list of the germ graph's edges
    germ_edges = germ.edges(data=True)

    # Create a list of sorted edges that are *not* in the germ
    # (because you don't want to add them in twice!)
    H_edges_sorted_not_germ = [edge for edge in H_edges_sorted
                               if edge not in germ_edges]
    # Calculate how many edges need to be added to reach the specified cost
    # and round to the nearest integer.
    n_edges = (cost/100.0) * len(H)*(len(H)-1)*0.5
    n_edges = np.int(np.around(n_edges))
    n_edges = n_edges - len(germ_edges)

    # If your cost is so small that your minimum spanning tree already covers
    # it then you can't do any better than the MST and you'll just have to
    # return it with an accompanying error message
    # A tree has n-1 edges and a complete graph has n(n − 1)/2 edges, so we
    # need cost/100 > 2/n, where n is the number of vertices
    if n_edges < 0:
        raise Exception('Unable to calculate matrix at this cost -\
                         minimum spanning tree is too large')
        print('cost must be >= {}'.format(2/len(H)))
    # Otherwise, add in the appropriate number of edges (n_edges)
    # from your sorted list (H_edges_sorted_not_germ)
    else:
        germ.add_edges_from(H_edges_sorted_not_germ[:n_edges])
    # And return the updated germ as your graph
    return scale_weights(germ)


def graph_at_cost(M, cost, mst=True):
    '''
    Returns a connected binary graph.

    First creates the minimum spanning tree for the graph, and then adds
    in edges according to their connection strength up to a particular cost.

    M should be an adjacency matrix as numpy array or dataframe.
    cost should be a number between 0 and 100
    '''
    # If dataframe, convert to array
    if isinstance(M, pd.DataFrame):
        array = M.values
    elif isinstance(M, np.ndarray):
        array = M
    else:
        raise TypeError(
              "expecting numpy array or pandas dataframe as first input")

    # Read this array into a graph G
    G = weighted_graph_from_matrix(array)
    return threshold_graph(G, cost, mst=mst)


def random_graph(G, Q=10):
    '''
    Return a connected random graph that preserves degree distribution
    by swapping pairs of edges (double edge swap).

    Inputs:
        G: networkx graph
        Q: constant that determines how many swaps to conduct
           for every edge in the graph
           Default Q =10

    Returns:
        R: networkx graph

    CAVEAT: If it is not possible in 15 attempts to create a
    connected random graph then this code will raise an error
    '''

    import networkx as nx

    # Copy the graph
    R = G.copy()

    # Calculate the number of edges and set a constant
    # as suggested in the nx documentation
    E = R.number_of_edges()

    # Start the counter for randomisation attempts and set connected to False
    attempt = 0
    connected = False

    # Keep making random graphs until they are connected
    while not connected and attempt < 15:
        # Now swap some edges in order to preserve the degree distribution
        nx.double_edge_swap(R, Q*E, max_tries=Q*E*10)

        # Check that this graph is connected! If not, start again
        connected = nx.is_connected(R)
        if not connected:
            attempt += 1

    if attempt == 15:
        raise Exception("** Failed to randomise graph in first 15 tries -\
                             Attempt aborted. Network is likely too sparse **")
    return R
