import collections

import torch
import torch.nn.functional as F
from torch.utils.data.dataloader import default_collate

from ..utils import DataContainer


def collate(batch, sample_per_gpu=1):
    """
    Put each data field into tensor/DataContainer with outer dimension
    batch size.

    Extend default_collate to add support for `:DataContainer`, There are
    3 cases.
    1. cpu_only = True, e.g., meta data
    2. cpu_only = False, stack = True, e.g., images tensors
    3. cpu_only = False, stack = False, e.g., gt bboxes

    Args:
        batch (list[dict] or tuple[dict]): a batch of samples that collect
            from dataset, each sample is a dict that output by `__getitem__`
            function in dataset.
        sample_per_gpu (int): number of samples in each gpu.

    Returns:
        collate_batch (list[dict] or tuple[dict])
    """
    if not isinstance(batch, collections.Sequence):
        raise TypeError("{} is not supported.".format(batch.dtype))

    if isinstance(batch[0], DataContainer):
        assert len(batch) % sample_per_gpu == 0
        stacked = []
        if batch[0].cpu_only:
            for i in range(0, len(batch), sample_per_gpu):
                stacked.append(
                    [sample.data for sample in batch[i:i + sample_per_gpu]])
            return DataContainer(
                stacked, batch[0].stack, batch[0].padding_value, cpu_only=True)
        elif batch[0].stack:
            for i in range(0, len(batch), sample_per_gpu):
                assert isinstance(batch[i].data, torch.Tensor)
                # TODO: handle tensors other than 3d
                assert batch[i].dim() == 3
                c, h, w = batch[0].size()
                for sample in batch[i:i + sample_per_gpu]:
                    assert c == sample.size(0)
                    h = max(h, sample.size(1))
                    w = max(w, sample.size(2))
                padded_samples = [
                    F.pad(
                        sample.data,
                        (0, w - sample.size(2), 0, h - sample.size(1)),
                        value=sample.padding_value)
                    for sample in batch[i:i + sample_per_gpu]
                ]
                stacked.append(default_collate(padded_samples))
        else:
            for i in range(0, len(batch), sample_per_gpu):
                stacked.append(
                    [sample.data for sample in batch[i:i + sample_per_gpu]])
        return DataContainer(stacked, batch[0].stack, batch[0].padding_value)
    elif isinstance(batch[0], collections.Sequence):
        transposed = zip(*batch)
        return [collate(samples, sample_per_gpu) for samples in transposed]
    elif isinstance(batch[0], collections.Mapping):
        return {
            key: collate([d[key] for d in batch], sample_per_gpu)
            for key in batch[0]
        }
    else:
        return default_collate(batch)
