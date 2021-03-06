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



def input_fn(bridge, trainer_master):
    dataset = flt.data.DataBlockLoader(256, 'follower', bridge, trainer_master)
    feature_map = {
        "example_id": tf.FixedLenFeature([], tf.string),
        "x": tf.FixedLenFeature([28 * 28 // 2], tf.float32),
    }
    record_batch = dataset.make_batch_iterator().get_next()
    features = tf.parse_example(record_batch, features=feature_map)
    return features, {}


def serving_input_receiver_fn():
    feature_map = {
        "example_id": tf.FixedLenFeature([], tf.string),
        "x": tf.FixedLenFeature([28 * 28 // 2], tf.float32),
    }
    record_batch = tf.placeholder(dtype=tf.string, name='examples')
    features = tf.parse_example(record_batch, features=feature_map)
    return tf.estimator.export.ServingInputReceiver(features,
                                                    {'examples': record_batch})


def model_fn(model, features, labels, mode):
    x = features['x']

    w1f = tf.get_variable('w1f',
                          shape=[28 * 28 / 2, 128],
                          dtype=tf.float32,
                          initializer=tf.random_uniform_initializer(
                              -0.01, 0.01))
    b1f = tf.get_variable('b1f',
                          shape=[128],
                          dtype=tf.float32,
                          initializer=tf.zeros_initializer())

    act1_f = tf.nn.relu(tf.nn.bias_add(tf.matmul(x, w1f), b1f))

    if mode == tf.estimator.ModeKeys.TRAIN:
        gact1_f = model.send('act1_f', act1_f, require_grad=True)
        optimizer = tf.train.GradientDescentOptimizer(0.1)
        train_op = model.minimize(
            optimizer,
            act1_f,
            grad_loss=gact1_f,
            global_step=tf.train.get_or_create_global_step())
        return model.make_spec(mode,
                               loss=tf.math.reduce_mean(act1_f),
                               train_op=train_op)
    elif mode == tf.estimator.ModeKeys.PREDICT:
        return model.make_spec(mode=mode, predictions={'act1_f': act1_f})


if __name__ == '__main__':
    parser = flt.trainer_worker.create_argument_parser()
    flt.trainer_worker.train(
        'follower', parser.parse_args(), input_fn,
        model_fn, serving_input_receiver_fn)
