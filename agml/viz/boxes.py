# Copyright 2021 UC Davis Plant AI and Biophysics Lab
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import cv2
import numpy as np
import matplotlib.pyplot as plt

from agml.utils.general import resolve_tuple_values, as_scalar, scalar_unpack
from agml.data.tools import (
    _resolve_coco_annotations, convert_bbox_format # noqa
)
from agml.viz.tools import (
    get_colormap, auto_resolve_image, format_image, show_when_allowed
)


def _resolve_proportional_bboxes(coords, shape):
    """Resolves float vs. integer bounding boxes."""
    coords = scalar_unpack(coords)
    if all(isinstance(i, float) for i in coords):
        if coords[0] <= 1:
            x, y, width, height = coords
            y *= shape[0]; height *= shape[0]  # noqa
            x *= shape[1]; width *= shape[1]  # noqa
            coords = [x, y, width, height]
        return [int(round(c)) for c in coords]
    elif all(isinstance(i, int) for i in coords):
        return coords
    raise TypeError(
        f"Got multiple types for coordinates: "
        f"{[type(i) for i in coords]}.")


@auto_resolve_image
def annotate_bboxes_on_image(
        image, bboxes = None, labels = None, bbox_format = None):
    """Annotates bounding boxes onto an image.

    Given an image with bounding boxes and labels, this method will
    annotate the bounding boxes directly onto the image (with category
    label). Bounding boxes are expected to be in COCO JSON format, that
    is, (`x_min`, `y_max`, `width`, `height`). Use the helper method
    `agml.data.convert_bboxes` to format your bounding boxes as such.

    Parameters
    ----------
    image : Any
        Either the image, or a tuple consisting of the image,
        bounding boxes, and (optional) labels.
    bboxes : Any
        The bounding boxes in COCO JSON format. This can be either
        a dictionary with COCO JSON annotations, or just the boxes.
    labels : Any
        Optional category labels for the bounding box color.
    bbox_format : optional
        The format of the bounding box (for non-COCO-JSON bounding
        boxes).  See `agml.data.convert_bbox_format` for information
        on the valid parameters for the format.

    Returns
    -------
    The annotated image.
    """
    image, bboxes, labels = resolve_tuple_values(
        image, bboxes, labels, custom_error =
        "If `image` is a tuple/list, it should contain "
        "three values: the image, mask, and (optionally) labels.")
    if isinstance(bboxes, dict):
        bboxes = _resolve_coco_annotations(bboxes)['bbox']
    image = np.asarray(format_image(image))
    if labels is None:
        labels = [1] * len(bboxes)
    if bbox_format is not None:
        bboxes = convert_bbox_format(bboxes, bbox_format)
    if not isinstance(bboxes[0], (list, np.ndarray)):
        bboxes = [bboxes]

    for bbox, label in zip(bboxes, labels):
        bbox = scalar_unpack(bbox)
        x1, y1, width, height = \
            _resolve_proportional_bboxes(bbox, image.shape)
        x2, y2 = x1 + width, y1 + height
        image = cv2.rectangle(
            image, (x1, y1), (x2, y2),
            get_colormap()[as_scalar(label)], 2)
    return image


@show_when_allowed
@auto_resolve_image
def visualize_image_and_boxes(
        image, bboxes = None, labels = None, bbox_format = None):
    """Visualizes an image with annotated bounding boxes.

    This method performs the same actions as `annotate_bboxes_on_image`,
    but simply displays the image once it has been formatted.

    Parameters
    ----------
    image : Any
        Either the image, or a tuple consisting of the image,
        bounding boxes, and (optional) labels.
    bboxes : Any
        The bounding boxes in COCO JSON format.
    labels : Any
        Optional category labels for the bounding box color.
    bbox_format : optional
        The format of the bounding box (for non-COCO-JSON bounding
        boxes).  See `agml.data.convert_bbox_format` for information
        on the valid parameters for the format.

    Returns
    -------
    The matplotlib figure with the image.
    """
    image, bboxes, labels = resolve_tuple_values(
        image, bboxes, labels, custom_error =
        "If `image` is a tuple/list, it should contain "
        "three values: the image, boxes, and (optionally) labels.")
    image = annotate_bboxes_on_image(image, bboxes, labels, bbox_format)

    plt.figure(figsize = (10, 10))
    plt.imshow(image)
    plt.gca().axis('off')
    plt.gca().set_aspect('equal')
    return plt.gcf()


@show_when_allowed
@auto_resolve_image
def visualize_real_and_predicted_bboxes(
        image, truth_boxes = None, predicted_boxes = None):
    """Visualizes an image with annotated bounding boxes.

    This method performs the same actions as `annotate_bboxes_on_image`,
    but simply displays the image once it has been formatted.

    Parameters
    ----------
    image : Any
        Either the image, or a tuple consisting of the image,
        bounding boxes, and (optional) labels.
    truth_boxes : Any
        The true bounding boxes in COCO JSON format.
    predicted_boxes : Any
        The predicted bounding boxes in COCO JSON format.

    Returns
    -------
    The matplotlib figure with the image.
    """
    image, truth_boxes, predicted_boxes = resolve_tuple_values(
        image, truth_boxes, predicted_boxes, custom_error =
        "If `image` is a tuple/list, it should contain "
        "three values: the image, truth boxes, and predicted boxes.")
    real_image = annotate_bboxes_on_image(image.copy(), truth_boxes)
    predicted_image = annotate_bboxes_on_image(image.copy(), predicted_boxes)

    # Create two side-by-side figures with the images.
    fig, axes = plt.subplots(1, 2, figsize = (10, 5))
    for ax, img, label in zip(
            axes, (real_image, predicted_image),
            ("Ground Truth Boxes", "Predicted Boxes")):
        ax.imshow(img)
        ax.set_axis_off()
        ax.set_title(label, fontsize = 15)
        ax.set_aspect('equal')
    fig.tight_layout()
    return fig

