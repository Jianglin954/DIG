import os
import torch
import pickle
import numpy as np
import os.path as osp
from torch_geometric.utils import dense_to_sparse
from torch_geometric.data import Data, InMemoryDataset, download_url, extract_zip
from torch_geometric.data.dataset import files_exist
import shutil


def read_ba2motif_data(folder: str, prefix):
    with open(os.path.join(folder, f"{prefix}.pkl"), 'rb') as f:
        dense_edges, node_features, graph_labels = pickle.load(f)

    data_list = []
    for graph_idx in range(dense_edges.shape[0]):
        data_list.append(Data(x=torch.from_numpy(node_features[graph_idx]).float(),
                              edge_index=dense_to_sparse(torch.from_numpy(dense_edges[graph_idx]))[0],
                              y=torch.from_numpy(np.where(graph_labels[graph_idx])[0])))
    return data_list


def read_syn_data(folder: str, prefix):
    with open(os.path.join(folder, f"{prefix}.pkl"), 'rb') as f:
        adj, features, y_train, y_val, y_test, train_mask, val_mask, test_mask, edge_label_matrix = pickle.load(f)

    x = torch.from_numpy(features).float()
    y = train_mask.reshape(-1, 1) * y_train + val_mask.reshape(-1, 1) * y_val + test_mask.reshape(-1, 1) * y_test
    y = torch.from_numpy(np.where(y)[1])
    edge_index = dense_to_sparse(torch.from_numpy(adj))[0]
    data = Data(x=x, y=y, edge_index=edge_index)
    data.train_mask = torch.from_numpy(train_mask)
    data.val_mask = torch.from_numpy(val_mask)
    data.test_mask = torch.from_numpy(test_mask)
    return data


class SynGraphDataset(InMemoryDataset):
    r"""
    The Synthetic datasets used in
    `Parameterized Explainer for Graph Neural Network <https://arxiv.org/abs/2011.04573>`_.
    It takes Barabási–Albert(BA) graph or balance tree as base graph
    and randomly attachs specific motifs to the base graph.

    Args:
        root (:obj:`str`): Root data directory to save datasets
        name (:obj:`str`): The name of the dataset. Including :obj:`BA_shapes`, BA_grid,
        transform (:obj:`Callable`, :obj:`None`): A function/transform that takes in an
            :class:`torch_geometric.data.Data` object and returns a transformed
            version. The data object will be transformed before every access.
            (default: :obj:`None`)
        pre_transform (:obj:`Callable`, :obj:`None`):  A function/transform that takes in
            an :class:`torch_geometric.data.Data` object and returns a
            transformed version. The data object will be transformed before
            being saved to disk. (default: :obj:`None`)

    """
    def __init__(self, root, name, transform=None, pre_transform=None):
        self.name = name
        super(SynGraphDataset, self).__init__(root, transform, pre_transform)
        self.data, self.slices = torch.load(self.processed_paths[0])

    @property
    def raw_dir(self):
        return osp.join(self.root, self.name, 'raw')

    @property
    def processed_dir(self):
        return osp.join(self.root, self.name, 'processed')

    @property
    def raw_file_names(self):
        return [f"{self.name}.pkl"]

    @property
    def processed_file_names(self):
        return ['data.pt']

    def process(self):

        if self.name.lower() == 'BA_2Motifs'.lower():
            data_list = read_ba2motif_data(self.raw_dir, self.name)

            if self.pre_filter is not None:
                data_list = [self.get(idx) for idx in range(len(self))]
                data_list = [data for data in data_list if self.pre_filter(data)]
                self.data, self.slices = self.collate(data_list)

            if self.pre_transform is not None:
                data_list = [self.get(idx) for idx in range(len(self))]
                data_list = [self.pre_transform(data) for data in data_list]
                self.data, self.slices = self.collate(data_list)
        else:
            # Read data into huge `Data` list.
            data = read_syn_data(self.raw_dir, self.name)
            data = data if self.pre_transform is None else self.pre_transform(data)
            data_list = [data]

        torch.save(self.collate(data_list), self.processed_paths[0])


class BA_LRP(InMemoryDataset):
    r"""
    The synthetic graph classification dataset used in
    `Higher-Order Explanations of Graph Neural Networks via Relevant Walks <https://arxiv.org/abs/2006.03589>`_.
    The first class in :class:`~BA_LRP` is Barabási–Albert(BA) graph which connects a new node :math:`\mathcal{V}` from
    current graph :math:`\mathcal{G}`.

    .. math:: p(\mathcal{V}) = \frac{Degree(\mathcal{V})}{\sum_{\mathcal{V}' \in \mathcal{G}} Degree(\mathcal{V}')}

    The second class in :class:`~BA_LRP` has a slightly higher growth model and nodes are selected
    without replacement with the inverse preferential attachment model.

    .. math:: p(\mathcal{V}) = \frac{Degree(\mathcal{V})}{\sum_{\mathcal{V}'^{-1} \in \mathcal{G}} Degree(\mathcal{V}')^{-1}}

    Args:
        root (:obj:`str`): Root data directory to save datasets
        num_per_class (:obj:`int`): The number of the graphs for each class.
        transform (:obj:`Callable`, :obj:`None`): A function/transform that takes in an
            :class:`torch_geometric.data.Data` object and returns a transformed
            version. The data object will be transformed before every access.
            (default: :obj:`None`)
        pre_transform (:obj:`Callable`, :obj:`None`):  A function/transform that takes in
            an :class:`torch_geometric.data.Data` object and returns a
            transformed version. The data object will be transformed before
            being saved to disk. (default: :obj:`None`)

    .. note:: :class:`~BA_LRP` will automatically generate the dataset
      if the dataset file is not existed in the root directory.
    """
    url = ('https://github.com/divelab/DIG_storage/raw/main/xgraph/datasets/ba_lrp/raw.pt')

    def __init__(self, root, num_per_class=10000, transform=None, pre_transform=None):
        self.name = 'ba_lrp'
        self.num_per_class = num_per_class
        super().__init__(root, transform, pre_transform)
        self.data, self.slices = torch.load(self.processed_paths[0])

    @property
    def raw_dir(self):
        return osp.join(self.root, self.name, 'raw')

    @property
    def processed_dir(self):
        return osp.join(self.root, self.name, 'processed')

    @property
    def raw_file_names(self):
        return [f"raw.pt"]

    @property
    def processed_file_names(self):
        return [f'data.pt']

    def download(self):
        url = self.url
        path = download_url(url, self.raw_dir)
        # extract_zip(path, self.raw_dir)
        # os.unlink(path)

    def gen_class1(self):
        x = torch.tensor([[1], [1]], dtype=torch.float)
        edge_index = torch.tensor([[0, 1], [1, 0]], dtype=torch.long)
        data = Data(x=x, edge_index=edge_index, y=torch.tensor([[0]], dtype=torch.float))

        for i in range(2, 20):
            data.x = torch.cat([data.x, torch.tensor([[1]], dtype=torch.float)], dim=0)
            deg = torch.stack([(data.edge_index[0] == node_idx).float().sum() for node_idx in range(i)], dim=0)
            sum_deg = deg.sum(dim=0, keepdim=True)
            probs = (deg / sum_deg).unsqueeze(0)
            prob_dist = torch.distributions.Categorical(probs)
            node_pick = prob_dist.sample().squeeze()
            data.edge_index = torch.cat([data.edge_index,
                                         torch.tensor([[node_pick, i], [i, node_pick]], dtype=torch.long)], dim=1)

        return data

    def gen_class2(self):
        x = torch.tensor([[1], [1]], dtype=torch.float)
        edge_index = torch.tensor([[0, 1], [1, 0]], dtype=torch.long)
        data = Data(x=x, edge_index=edge_index, y=torch.tensor([[1]], dtype=torch.float))
        epsilon = 1e-30

        for i in range(2, 20):
            data.x = torch.cat([data.x, torch.tensor([[1]], dtype=torch.float)], dim=0)
            deg_reciprocal = torch.stack([1 / ((data.edge_index[0] == node_idx).float().sum() + epsilon) for node_idx in range(i)], dim=0)
            sum_deg_reciprocal = deg_reciprocal.sum(dim=0, keepdim=True)
            probs = (deg_reciprocal / sum_deg_reciprocal).unsqueeze(0)
            prob_dist = torch.distributions.Categorical(probs)
            node_pick = -1
            for _ in range(1 if i % 5 != 4 else 2):
                new_node_pick = prob_dist.sample().squeeze()
                while new_node_pick == node_pick:
                    new_node_pick = prob_dist.sample().squeeze()
                node_pick = new_node_pick
                data.edge_index = torch.cat([data.edge_index,
                                             torch.tensor([[node_pick, i], [i, node_pick]], dtype=torch.long)], dim=1)

        return data

    def process(self):
        if files_exist(self.raw_paths):
            shutil.copyfile(self.raw_paths[0], self.processed_paths[0])
            return

        data_list = []
        for i in range(self.num_per_class):
            data_list.append(self.gen_class1())
            data_list.append(self.gen_class2())

        data, slices = self.collate(data_list)
        torch.save((data, slices), self.processed_paths[0])
