import sys
sys.path.append('./')

# tensorflow messageの抑制
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import tensorflow as tf
import numpy as np
import pandas as pd
import pickle

from utils.datasets import load_data, train_test_split
from utils.train import training_mixup
from utils.data_augment import random_flip_left_right, random_rotate_90, gen_random_cutout
from utils.common import time_counter

import models.wrapper
import models.wrapper_T

tfk = tf.keras
tfk.backend.set_floatx('float32')

# Params
n_classes = 3
batch_size = 64
n_epochs = 100
# lr = 0.001

# Dataset
print('[Dataset]')
with time_counter():
    with open('train_size128.pkl', 'rb') as fp:
        x_train, y_train = pickle.load(fp)
    with open('test_size128.pkl', 'rb') as fp:
        x_test, y_test = pickle.load(fp)
    n_train = len(x_train)

    _random_cutout = gen_random_cutout(42)
    @tf.function
    def augment(image, label):
        image, label = random_flip_left_right(image, label)
        # image, label = random_flip_up_down(image, label)
        image, label =_random_cutout(image, label)
        image, label = random_rotate_90(image, label)
        return image, label

    train_ds = tf.data.Dataset.from_tensor_slices((x_train, y_train)) \
        .shuffle(n_train).map(augment) \
        .batch(batch_size).repeat(3)    # datasetのサイズを3倍に
    test_ds = tf.data.Dataset.from_tensor_slices((x_test, y_test)).batch(batch_size)
print('x_train: {}'.format(x_train.shape))
print('y_train: {}'.format(y_train.shape))
print('x_test: {}'.format(x_test.shape))
print('y_test: {}'.format(y_test.shape))

in_shape = x_train.shape[1:]

# grad-camようにダンプ
with open('test_ds.pkl', 'wb') as fp:
    pickle.dump((x_test, y_test), fp, protocol=4)

del x_train, y_train, x_test, y_test

models_and_params = {
    'vgg16': (models.wrapper.VGG16(weights=None, classes=3, input_shape=in_shape), 1e-5, 0.2, False),
    'resnet50': (models.wrapper.ResNet50(weights=None, classes=3, input_shape=in_shape), 8.7e-5, 0.2, False),
    'inceptionv3': (models.wrapper.InceptionV3(weights=None, classes=3, input_shape=in_shape), 7.9e-5, 0.2, False),
    'densenet121': (models.wrapper.DenseNet121(weights=None, classes=3, input_shape=in_shape), 7.1e-5, 0.2, False),
    'inceptionresnetv2': (models.wrapper.InceptionResNetV2(weights=None, classes=3, input_shape=in_shape), 5.5e-5, 0.2, False),
    'efficientnetb0': (models.efficientnet.tfkeras.EfficientNetB0(weights=None, classes=3, input_shape=in_shape), 5e-3, 0.2, False),

    'vgg16_pretrained': (models.wrapper_T.VGG16(classes=3, input_shape=in_shape), 1e-5, 0.2, True),
    'resnet50_pretraind': (models.wrapper_T.ResNet50(classes=3, input_shape=in_shape), 8.7e-5, 0.2, True),
    'inceptionv3_pretrained': (models.wrapper_T.InceptionV3(classes=3, input_shape=in_shape), 7.9e-5, 0.2, True),
    'densenet121_pretrained': (models.wrapper_T.DenseNet121(classes=3, input_shape=in_shape), 7.1e-5, 0.2, True),
    'inceptionresnetv2_pretrained': (models.wrapper_T.InceptionResNetV2(classes=3, input_shape=in_shape), 5.5e-5, 0.2,  True),
    'efficientnetb0_pretraind': (models.wrapper_T.EfficientNetB0(classes=3, input_shape=in_shape), 5e-3, 0.2, True),

    'vgg16_ft': (models.wrapper_T.VGG16(classes=3, input_shape=in_shape), 1e-5, 0.2, False),
    'resnet50_ft': (models.wrapper_T.ResNet50(classes=3, input_shape=in_shape), 8.7e-5, 0.2, False),
    'inceptionv3_ft': (models.wrapper_T.InceptionV3(classes=3, input_shape=in_shape), 7.9e-5, 0.2, False),
    'densenet121_ft': (models.wrapper_T.DenseNet121(classes=3, input_shape=in_shape), 7.1e-5, 0.2, False),
    'inceptionresnetv2_ft': (models.wrapper_T.InceptionResNetV2(classes=3, input_shape=in_shape), 5.5e-5, 0.2, False),
    'efficientnetb0_ft': (models.wrapper_T.EfficientNetB0(classes=3, input_shape=in_shape), 5e-3, 0.2, False),
}

# Loss
loss = tfk.losses.CategoricalCrossentropy()

# Validating
for model_name in models_and_params:
    model, lr, alpha, pretrained = models_and_params[model_name]
    opt = tfk.optimizers.Adam(lr)

    weight_name = 'best_param_{}'.format(model_name)
    if not pretrained:
        hist = training_mixup(model, train_ds, test_ds, loss, opt, n_epochs, batch_size, n_classes, alpha=alpha, output_best_weights=True, weight_name=weight_name)
    else:
        train_weights = model.layers[1].trainable_variables
        hist = training_mixup(model, train_ds, test_ds, loss, opt, n_epochs, batch_size, n_classes, alpha=alpha, output_best_weights=True, weight_name=weight_name, train_weights=train_weights)

    pd.DataFrame(hist).to_csv('history_{}.csv'.format(model_name))
    
