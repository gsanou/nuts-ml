"""
.. module:: cnn_train
   :synopsis: Example nuts-ml pipeline for training a CNN on MNIST
"""

import torch
import torch.nn.functional as F
import torch.nn as nn
import torch.optim as optim
import nutsflow as nf
import nutsml as nm
import numpy as np

from nutsml.network import PytorchNetwork
from utils import download_mnist, load_mnist




class Flatten(nn.Module):
    """Flatten layer"""

    def __init__(self):
        super(Flatten, self).__init__()

    def forward(self, x):
        x = x.view(x.size(0), -1)
        return x


class Model(nn.Module):
    """CNN model"""

    def __init__(self, device='cpu'):
        super(Model, self).__init__()

        self.layers = nn.Sequential(
            nn.Conv2d(1, 10, kernel_size=5),
            nn.MaxPool2d(2),
            nn.ReLU(),
            nn.Conv2d(10, 20, kernel_size=5),
            nn.Dropout(),
            nn.MaxPool2d(2),
            nn.ReLU(),
            Flatten(),
            nn.Linear(320, 50),
            nn.ReLU(),
            nn.Dropout(),
            nn.Linear(50, 10),
        )

        # required properties of a model to be wrapped as PytorchNetwork!
        self.device = device  # 'cuda', 'cuda:0' or 'gpu'
        self.losses = F.cross_entropy  # can be list of loss functions
        self.optimizer = optim.Adam(self.parameters())

    def forward(self, x):
        """Forward pass through network for input x"""
        return self.layers(x)


# definition of nuts
BATCHSIZE = 64
build_batch = (nm.BuildBatch(BATCHSIZE, verbose=False)
               .input(0, 'image', 'float32', True)
               .output(1, 'number', 'int64'))
build_pred_batch = (nm.BuildBatch(BATCHSIZE, verbose=False)
                    .input(0, 'image', 'float32', True))
augment = (nm.AugmentImage(0)
           .by('identical', 1)
           .by('translate', 0.2, [-3, +3], [-3, +3])
           .by('rotate', 0.2, [-30, +30])
           .by('shear', 0.2, [0, 0.2])
           .by('elastic', 0.2, [5, 5], [100, 100], [0, 100])
           )
vec2img = nf.MapCol(0, lambda x: (x.reshape([28, 28]) * 255).astype('uint8'))
sample_gen = lambda x, y: zip(iter(x), iter(y))


def accuracy(y_true, y_pred):
    """Compute accuracy"""
    from sklearn.metrics import accuracy_score
    return accuracy_score(y_true, np.array(y_pred).argmax(1))


def train(network, x, y, epochs=3):
    """Train network for given number of epochs"""
    for epoch in range(epochs):
        print('epoch', epoch + 1)
        losses = (sample_gen(x, y) >> nf.PrintProgress(x) >> vec2img >>
                  augment >> nf.Shuffle(1000) >> build_batch >>
                  network.train() >> nf.Collect())
        print('train loss:', np.mean(losses))


def validate(network, x, y):
    """Compute validation/test loss (= mean over batch losses)"""
    losses = (sample_gen(x, y) >> nf.PrintProgress(x) >> vec2img >>
              build_batch >> network.validate() >> nf.Collect())
    print('val loss:', np.mean(losses))


def predict(network, x, y):
    """Compute network outputs and print accuracy"""
    preds = (sample_gen(x, y) >> nf.PrintProgress(x) >> vec2img >>
             build_pred_batch >> network.predict() >> nf.Collect())
    acc = accuracy(y, preds)
    print('test acc', 100.0 * acc)


def evaluate(network, x, y):
    """Evaluate network performance (here accuracy)"""
    metrics = [accuracy]
    result = (sample_gen(x, y) >> nf.PrintProgress(x) >> vec2img >>
              build_batch >> network.evaluate(metrics))
    print(result)


def view_misclassified_images(network, x, y):
    """Show misclassified images"""
    make_label = nf.Map(lambda s: (s[0], 'true:%d  pred:%d' % (s[1], s[2])))
    filter_error = nf.Filter(lambda s: s[1] != s[2])
    view_image = nm.ViewImageAnnotation(0, 1, pause=1)

    preds = (sample_gen(x, y) >> vec2img >> build_pred_batch >>
             network.predict() >> nf.Map(np.argmax) >> nf.Collect())
    (zip(x, y, preds) >> vec2img >> filter_error >> make_label >>
     view_image >> nf.Consume())


def view_augmented_images(x, y, n=10):
    """Show n augmented images"""
    view_image = nm.ViewImageAnnotation(0, 1, pause=1)
    zip(x, y) >> vec2img >> augment >> nf.Take(n) >> view_image >> nf.Consume()


if __name__ == '__main__':
    print('loading data...')
    filepath = download_mnist()
    x_train, y_train, x_test, y_test = load_mnist(filepath)

    # print('viewing images...')
    # view_augmented_images(x_test, y_test)

    print('creating model...')
    device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
    model = Model(device)
    network = PytorchNetwork(model)
    # network.load_weights()
    network.print_layers((1, 28, 28))

    print('training ...')
    train(network, x_train, y_train, epochs=3)
    network.save_weights()

    print('validating ...')
    validate(network, x_test, y_test)

    print('predicting ...')
    predict(network, x_test, y_test)

    print('evaluating ...')
    evaluate(network, x_test, y_test)

    # print('showing errors ...')
    # view_misclassified_images(network, x_test, y_test)
