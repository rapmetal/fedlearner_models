# Copyright 2020 The FedLearner Authors. All Rights Reserved.
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

# coding: utf-8
# pylint: disable=no-else-return, inconsistent-return-statements

import tensorflow.compat.v1 as tf
import fedlearner.trainer as flt


parser = flt.trainer_worker.create_argument_parser()
args = parser.parse_args()

def input_fn(bridge, trainer_master):
    dataset = flt.data.DataBlockLoader(256, 'leader', bridge, trainer_master)
    feature_map = {
        "example_id": tf.FixedLenFeature([], tf.string),
        "x": tf.FixedLenFeature([28 * 28 // 2], tf.float32),
        "y": tf.FixedLenFeature([], tf.int64)
    }
    record_batch = dataset.make_batch_iterator().get_next()
    features = tf.parse_example(record_batch, features=feature_map)
    labels = {'y': features.pop('y')}
    return features, labels


def serving_input_receiver_fn():
    feature_map = {
        "example_id": tf.FixedLenFeature([], tf.string),
        "x": tf.FixedLenFeature([28 * 28 // 2], tf.float32),
    }
    record_batch = tf.placeholder(dtype=tf.string, name='examples')
    features = tf.parse_example(record_batch, features=feature_map)
    features['act1_f'] = tf.placeholder(dtype=tf.float32, name='act1_f')
    receiver_tensors = {'examples': record_batch, 'act1_f': features['act1_f']}
    return tf.estimator.export.ServingInputReceiver(features, receiver_tensors)


def model_fn(model, features, labels, mode):
    x = features['x']

    w1l = tf.get_variable('w1l',
                          shape=[28 * 28 // 2, 128],
                          dtype=tf.float32,
                          initializer=tf.random_uniform_initializer(
                              -0.01, 0.01))
    b1l = tf.get_variable('b1l',
                          shape=[128],
                          dtype=tf.float32,
                          initializer=tf.zeros_initializer())
    w2 = tf.get_variable('w2',
                         shape=[128 * 2, 10],
                         dtype=tf.float32,
                         initializer=tf.random_uniform_initializer(
                             -0.01, 0.01))
    b2 = tf.get_variable('b2',
                         shape=[10],
                         dtype=tf.float32,
                         initializer=tf.zeros_initializer())

    act1_l = tf.nn.relu(tf.nn.bias_add(tf.matmul(x, w1l), b1l))
    if mode == tf.estimator.ModeKeys.TRAIN:
        act1_f = model.recv('act1_f', tf.float32, require_grad=True)
    else:
        act1_f = features['act1_f']
    act1 = tf.concat([act1_l, act1_f], axis=1)
    logits = tf.nn.bias_add(tf.matmul(act1, w2), b2)

    if mode == tf.estimator.ModeKeys.TRAIN:
        y = labels['y']
        loss = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=y,
                                                              logits=logits)
        loss = tf.math.reduce_mean(loss)

        optimizer = tf.train.GradientDescentOptimizer(0.1)
        train_op = model.minimize(
            optimizer, loss, global_step=tf.train.get_or_create_global_step())

        correct = tf.nn.in_top_k(predictions=logits, targets=y, k=1)
        acc = tf.reduce_mean(input_tensor=tf.cast(correct, tf.float32))

        logging_hook = tf.train.LoggingTensorHook(
            {"loss" : loss, "acc" : acc}, every_n_iter=10)

        return model.make_spec(
            mode=mode, loss=loss, train_op=train_op,
            training_hooks=[logging_hook])
    elif mode == tf.estimator.ModeKeys.PREDICT:
        return model.make_spec(mode=mode, predictions=logits)


if __name__ == '__main__':
    flt.trainer_worker.train(
        'leader', args, input_fn,
        model_fn, serving_input_receiver_fn)
