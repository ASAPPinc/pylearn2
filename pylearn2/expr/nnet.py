"""
Useful expressions common to many neural network applications.
"""
__authors__ = "Ian Goodfellow"
__copyright__ = "Copyright 2010-2013, Universite de Montreal"
__credits__ = ["Ian Goodfellow"]
__license__ = "3-clause BSD"
__maintainer__ = "LISA Lab"
__email__ = "pylearn-dev@googlegroups"

import numpy as np
import theano
from theano.printing import Print
from theano import tensor as T
from theano.gof.op import get_debug_values


def softmax_numpy(x):
    """
    NumpPy implementation of the softmax function.

    Parameters
    ----------
    x : ndarray
        Should have two dimensions

    Returns
    -------
    rval : ndarray
        rval[i,:] is the softmax of x[i,:]
    """
    stable_x = (x.T - x.max(axis=1)).T
    numer = np.exp(stable_x)
    return (numer.T / numer.sum(axis=1)).T


def pseudoinverse_softmax_numpy(x):
    """
    NumPy implementation of a pseudo-inverse of the softmax function.

    Parameters
    ----------
    x : vector

    Returns
    -------
    y : vector
        softmax(y) = x

    Notes
    -----
    This problem is underdetermined, so we also impose y.mean() = 0
    """
    rval = np.log(x)
    rval -= rval.mean()
    return rval


def sigmoid_numpy(x):
    """
    NumPy implementation of the logistic sigmoid function.

    Parameters
    ----------
    x : ndarray
        Arguments to the logistic sigmoid function

    Returns
    -------
    y : ndarray
        The output of the logistic sigmoid function applied
        element-wise to x
    """
    assert not isinstance(x, theano.gof.Variable)
    return 1. / (1. + np.exp(-x))


def inverse_sigmoid_numpy(x):
    """
    NumPy implementation of the inverse of the logistic sigmoid function.

    Parameters
    ----------
    x : ndarray
        An array of values in the interval (0, 1)

    Returns
    -------
    y: ndarray
        An array of values such that sigmoid_numpy(y) ~=~ x
    """
    return np.log(x / (1. - x))


def arg_of_softmax(Y_hat):
    """
    Given the output of a call to theano.tensor.nnet.softmax,
    returns the argument to the softmax (by tracing the Theano
    graph).

    Parameters
    ----------
    Y_hat : Variable
        softmax(Z)

    Returns
    -------
    Z : Variable
        The variable that was passed to the Softmax op to create `Y_hat`.
        Raises an error if `Y_hat` is not actually the output of a
        Softmax.
    """
    assert hasattr(Y_hat, 'owner')
    owner = Y_hat.owner
    assert owner is not None
    op = owner.op
    if isinstance(op, Print):
        assert len(owner.inputs) == 1
        Y_hat, = owner.inputs
        owner = Y_hat.owner
        op = owner.op
    if not isinstance(op, T.nnet.Softmax):
        raise ValueError("Expected Y_hat to be the output of a softmax, "
                         "but it appears to be the output of " + str(op) +
                         " of type " + str(type(op)))
    z, = owner.inputs
    assert z.ndim == 2
    return z


def arg_of_sigmoid(Y_hat):
    """
    Given the output of a call to theano.tensor.nnet.sigmoid,
    returns the argument to the sigmoid (by tracing the Theano
    graph).

    Parameters
    ----------
    Y_hat : Variable
        T.nnet.sigmoid(Z)

    Returns
    -------
    Z : Variable
        The variable that was passed to T.nnet.sigmoid to create `Y_hat`.
        Raises an error if `Y_hat` is not actually the output of a theano
        sigmoid.
    """
    assert hasattr(Y_hat, 'owner')
    owner = Y_hat.owner
    assert owner is not None
    op = owner.op
    if isinstance(op, Print):
        assert len(owner.inputs) == 1
        Y_hat, = owner.inputs
        owner = Y_hat.owner
        op = owner.op
    success = False
    if isinstance(op, T.Elemwise):
        if isinstance(op.scalar_op, T.nnet.sigm.ScalarSigmoid):
            success = True
    if not success:
        raise TypeError("Expected Y_hat to be the output of a sigmoid, "
                        "but it appears to be the output of " + str(op) +
                        " of type " + str(type(op)))
    z, = owner.inputs
    assert z.ndim == 2
    return z


def kl(Y, Y_hat, batch_axis):
    """
    Warning: This function expects a sigmoid nonlinearity in the
    output layer. Returns a batch (vector) of mean across units of
    KL divergence for each example,
    KL(P || Q) where P is defined by Y and Q is defined by Y_hat:

    p log p - p log q + (1-p) log (1-p) - (1-p) log (1-q)
    For binary p, some terms drop out:
    - p log q - (1-p) log (1-q)
    - p log sigmoid(z) - (1-p) log sigmoid(-z)
    p softplus(-z) + (1-p) softplus(z)

    Parameters
    ----------
    Y : Variable
        targets for the sigmoid outputs. Currently Y must be purely binary.
        If it's not, you'll still get the right gradient, but the
        value in the monitoring channel will be wrong.
    Y_hat : Variable
        predictions made by the sigmoid layer. Y_hat must be generated by
        fprop, i.e., it must be a symbolic sigmoid.
    batch_axis : list
        list of axes to compute average kl divergence across.

    Returns
    -------
    ave : Variable
        average kl divergence between Y and Y_hat.
    """

    assert hasattr(Y_hat, 'owner')
    assert batch_axis is not None

    owner = Y_hat.owner
    assert owner is not None
    op = owner.op

    if not hasattr(op, 'scalar_op'):
        raise ValueError("Expected Y_hat to be generated by an Elemwise "
                         "op, got "+str(op)+" of type "+str(type(op)))
    assert isinstance(op.scalar_op, T.nnet.sigm.ScalarSigmoid)

    for Yv in get_debug_values(Y):
        if not (Yv.min() >= 0.0 and Yv.max() <= 1.0):
            raise ValueError("Expected Y to be between 0 and 1. Either Y"
                             + "< 0 or Y > 1 was found in the input.")

    z, = owner.inputs

    term_1 = Y * T.nnet.softplus(-z)
    term_2 = (1 - Y) * T.nnet.softplus(z)

    total = term_1 + term_2
    naxes = total.ndim
    axes_to_reduce = list(range(naxes))
    del axes_to_reduce[batch_axis]
    ave = total.mean(axis=axes_to_reduce)

    return ave


def elemwise_kl(Y, Y_hat):
    """
    Warning: This function expects a sigmoid nonlinearity in the
    output layer. Returns a batch (vector) of mean across units of
    KL divergence for each example,
    KL(P || Q) where P is defined by Y and Q is defined by Y_hat:

    p log p - p log q + (1-p) log (1-p) - (1-p) log (1-q)
    For binary p, some terms drop out:
    - p log q - (1-p) log (1-q)
    - p log sigmoid(z) - (1-p) log sigmoid(-z)
    p softplus(-z) + (1-p) softplus(z)

    Parameters
    ----------
    Y : Variable
        targets for the sigmoid outputs. Currently Y must be purely binary.
        If it's not, you'll still get the right gradient, but the
        value in the monitoring channel will be wrong.
    Y_hat : Variable
        predictions made by the sigmoid layer. Y_hat must be generated by
        fprop, i.e., it must be a symbolic sigmoid.

    Returns
    -------
    ave : Variable
        kl divergence between Y and Y_hat.
    """
    assert hasattr(Y_hat, 'owner')

    owner = Y_hat.owner
    assert owner is not None
    op = owner.op

    if not hasattr(op, 'scalar_op'):
        raise ValueError("Expected Y_hat to be generated by an Elemwise "
                         "op, got "+str(op)+" of type "+str(type(op)))
    assert isinstance(op.scalar_op, T.nnet.sigm.ScalarSigmoid)

    for Yv in get_debug_values(Y):
        if not (Yv.min() >= 0.0 and Yv.max() <= 1.0):
            raise ValueError("Expected Y to be between 0 and 1. Either Y"
                             + "< 0 or Y > 1 was found in the input.")

    z, = owner.inputs

    term_1 = Y * T.nnet.softplus(-z)
    term_2 = (1 - Y) * T.nnet.softplus(z)

    total = term_1 + term_2

    return total


def softmax_ratio(numer, denom):
    """
    .. todo::

        WRITEME properly

    Parameters
    ----------
    numer : Variable
        Output of a softmax.
    denom : Variable
        Output of a softmax.

    Returns
    -------
    ratio : Variable
        numer / denom, computed in a numerically stable way
    """

    numer_Z = arg_of_softmax(numer)
    denom_Z = arg_of_softmax(denom)
    numer_Z -= numer_Z.max(axis=1).dimshuffle(0, 'x')
    denom_Z -= denom_Z.min(axis=1).dimshuffle(0, 'x')

    new_num = T.exp(numer_Z - denom_Z) * (T.exp(denom_Z).sum(
        axis=1).dimshuffle(0, 'x'))
    new_den = (T.exp(numer_Z).sum(axis=1).dimshuffle(0, 'x'))

    return new_num / new_den


def compute_precision(tp, fp):
    """
    Computes the precision for the binary decisions.
    Computed as tp/(tp + fp).

    Parameters
    ----------
    tp : Variable
        True positives.
    fp : Variable
        False positives.

    Returns
    -------
    precision : Variable
        Precision of the binary classifications.
    """
    precision = tp / T.maximum(1., tp + fp)
    return precision


def compute_recall(y, tp):
    """
    Computes the recall for the binary classification.

    Parameters
    ----------
    y : Variable
        Targets for the binary classifications.
    tp : Variable
        True positives.

    Returns
    -------
    recall : Variable
        Recall for the binary classification.
    """
    recall = tp / T.maximum(1., y.sum())
    return recall


def compute_f1(precision, recall):
    """
    Computes the f1 score for the binary classification.
    Computed as,

    f1 = 2 * precision * recall / (precision + recall)

    Parameters
    ----------
    precision : Variable
        Precision score of the binary decisions.
    recall : Variable
        Recall score of the binary decisions.

    Returns
    -------
    f1 : Variable
        f1 score for the binary decisions.
    """
    f1 = (2. * precision * recall /
          T.maximum(1, precision + recall))
    return f1
