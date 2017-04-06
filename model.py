
import tensorflow as tf
from summary_manager import SummaryManager
from h_var import HVar
from experiments_manager import ExperimentsManager

import utils
from utils import check_create_dir
from tensorflow.python.ops import data_flow_ops

class FCLayer:
    def __init__(self, input, n_in, n_out, model, prefix):
        with tf.variable_scope(prefix):
            #print 'prefix = ' + str(prefix)
            self.W = model.hvar_mgr.create_var(tf.Variable(tf.random_normal([n_in, n_out], seed=1), name='W'))

            self.b = model.hvar_mgr.create_var(tf.Variable(tf.zeros([n_out]), name='b'))
            a = tf.matmul(input, self.W.out()) + self.b.out()

            # W = tf.Variable(tf.random_normal([n_in, n_out]), name='W')
            # b = tf.Variable(tf.zeros([n_out]), name='b')
            # a = tf.matmul(input, W) + b

            self.out = tf.nn.tanh(a)

    def print_params(self, sess):
        print 'W = ' + str(sess.run(self.W.var))
        #print 'b = ' + str(sess.run(self.b.var))
        print 'W.out = ' + str(sess.run(self.W.out()))


#This holds the model symbols
class Model(object):

    def print_layer_params(self, sess, i):
         self.layers[i].print_params(sess)

    class HVarManager:
        def __init__(self, model):
            self.all_hvars = []
            self.model = model

        def create_var(self, var):
            res = HVar(var, self.model)
            self.all_hvars.append(res)

            #print 'res.var.name = ' + str(res.var.name)
            name = res.var.name.split(":")[0].split("/")[-1]
            #print 'name = ' + str(name)
            with tf.name_scope(name):
                for alpha in res.history_aplha:
                    tmp = tf.summary.histogram('history_aplhas', alpha)
                    #print 'alpha name = ' + str(tmp.name)
                    self.model.summary_mgr.add_iter_summary(tmp)

                for alpha in res.replicas_aplha:
                    self.model.summary_mgr.add_iter_summary(tf.summary.histogram('replicas_aplha', alpha))

            return res

        def reset(self):
            self.all_hvars = []

        # the alphas from sesop (the coefitients that choose the history vector)
        def all_trainable_alphas(self):
            alphas = []
            for hvar in self.all_hvars:
                alphas.extend(hvar.replicas_aplha + hvar.history_aplha)
            return alphas

        # all the regular weights to be trained
        def all_trainable_weights(self):
            weights = []
            for hvar in self.all_hvars:
                weights.append(hvar.var)
            return weights

        def all_history_update_ops(self):
            print 'e = ' + str(self.model.experiment)
            b4_sesop = []
            after_sesop = []
            for hvar in self.all_hvars:
                b4, after = hvar.update_history_op()
                b4_sesop.append(b4)
                after_sesop.append(after)

            return b4_sesop, after_sesop

    def dump_checkpoint(self, sess):
        path = self.experiment.get_model_checkpoint_dir(self.node_id)
        if self.saver is None:

            check_create_dir(path)
            self.saver = tf.train.Saver(self.hvar_mgr.all_trainable_alphas() + self.hvar_mgr.all_trainable_weights())

        self.saver.save(sess, path + '/model.save', global_step=None)

    def init_from_checkpoint(self, sess):
        path = self.experiment.get_model_checkpoint_dir(self.node_id)
        if self.saver is None:
            self.saver = tf.train.Saver(self.hvar_mgr.all_trainable_alphas() + self.hvar_mgr.all_trainable_weights())


        self.saver.restore(sess, path)


    #self dontate a batch to be used by all.
    def get_shared_feed(self, sess, batch_size, is_train, models):
        x, y = self.batch_provider.next_batch(sess, batch_size, is_train)
        res = {self.input: x, self.label: y}
        for m in models:
            res[m.input] = x
            res[m.label] = y

        return res


    def __init__(self, experiment, batch_provider, node_id):
        self.experiment = experiment
        self.node_id = node_id
        self.saver = None
        #print 'node_id = ' + str(node_id)
        #print '-------------------------'

        self.hvar_mgr = Model.HVarManager(self)  # every experiment has its own hvar collection and summary collection.

        self.tensorboard_dir = ExperimentsManager().get_experiment_model_tensorboard_dir(self.experiment, self.node_id)
        self.summary_mgr = SummaryManager(self.tensorboard_dir)


        self.batch_provider = batch_provider



        self.loss_placeholder = tf.placeholder(dtype=tf.float32, shape=[], name='loss_placeholder')
        self.loss_b4_minus_after = tf.summary.scalar('loss_b4_minus_after', self.loss_placeholder)

        self.i = 0
        self.j = 0

        #self.input = tf.placeholder(dtype=tf.float32, name='input_placeholder')
        #self.label = tf.placeholder(dtype=tf.float32, name='output_placeholder')

        utils.printInfo(' self.batch_provider.batch() = ' + str( self.batch_provider.batch()))

        #Use stageing area:
        stager = data_flow_ops.StagingArea([tf.float32, tf.float32])
        self.stage = stager.put(self.batch_provider.batch())
        self.input, self.label = stager.get() #self.batch_provider.batch()
        #self.input, self.label = self.batch_provider.batch()


        # if not (self.experiment.getFlagValue('hSize') == 0 ) and self.node_id == 0:
        #     #print 'experiment = ' + str(experiment)
        #     self.mergered_summeries = self.summary_mgr.merge_iters()

        utils.printInfo('Dumping into tensorboard ' + str(self.tensorboard_dir))

    def log_loss_b4_minus_after(self, sess, loss_b4_minus_after):
        s = sess.run(self.loss_b4_minus_after, {self.loss_placeholder: loss_b4_minus_after})
        self.summary_mgr.writer.add_summary(s, self.j)
        self.j += 1

    # def dump_to_tensorboard(self, sess):
    #     if (self.experiment.getFlagValue('hSize') == 0) or self.node_id != 0:
    #         return
    #     #print 'Dumping into tensorboard ' + str(self.tensorboard_dir)
    #
    #     s = sess.run(self.mergered_summeries)
    #     self.summary_mgr.writer.add_summary(s, self.i)
    #
    #     self.i += 1

    def push_to_master_op(self):
        assert (self.node_id != 0)
        return [hvar.push_to_master_op() for hvar in self.hvar_mgr.all_hvars]

    def pull_from_master_op(self):
        assert (self.node_id != 0)
        return [hvar.pull_from_master_op() for hvar in self.hvar_mgr.all_hvars]

    def loss(self):
        return self._loss

    def get_batch_provider(self):
        return self.batch_provider

    def get_inputs(self):
        return self.input, self.label




#This holds the model symbols
class SimpleModel(Model):

    def __init__(self, experiment, batch_provider, node_id):
        super(SimpleModel, self).__init__(experiment, batch_provider, node_id)
        assert (experiment.getFlagValue('model') == 'simple')


        input_dim = experiment.getFlagValue('dim')
        output_dim = experiment.getFlagValue('output_dim')

        hidden_layers_num = experiment.getFlagValue('hidden_layers_num')
        hidden_layers_size = experiment.getFlagValue('hidden_layers_size')

        #build layers:
        self.layers = []
        self.layers.append(FCLayer(self.input, input_dim, hidden_layers_size, self, 'FC_'  + str(len(self.layers))))
        for i in range(hidden_layers_num):
            self.layers.append(FCLayer(self.layers[-1].out, hidden_layers_size, hidden_layers_size, self, 'FC_' + str(len(self.layers))))
        self.layers.append(FCLayer(self.layers[-1].out, hidden_layers_size, 1, self, 'FC_' + str(len(self.layers))))

        self.model_out = self.layers[-1].out

        # when log is true we build a model for training!

        loss_per_sample = tf.squared_difference(self.model_out, self.label, name='loss_per_sample')
        self._loss = tf.reduce_mean(loss_per_sample, name='loss')




from resnet_model import ResNet, HParams

#This holds the model symbols
class MnistModel(Model):

    def __init__(self, experiment, batch_provider, node_id):
        super(MnistModel, self).__init__(experiment, batch_provider, node_id)
        assert (experiment.getFlagValue('model') == 'mnist')

        hps = HParams(batch_size=None,
                      num_classes=10,
                      min_lrn_rate=0.0001,
                      lrn_rate=0.1,
                      num_residual_units=5,
                      use_bottleneck=False,
                      weight_decay_rate=0.0002,
                      relu_leakiness=0.1,
                      optimizer=None)

        def get_variable(name,
                 shape=None,
                 dtype=None,
                 initializer=None,
                 regularizer=None,
                 trainable=True,
                 collections=None,
                 caching_device=None,
                 partitioner=None,
                 validate_shape=True,
                 custom_getter=None):

            var = tf.get_variable(name, shape, dtype, initializer, regularizer, trainable, collections, caching_device,
                            partitioner, validate_shape, custom_getter)
            h_var = self.hvar_mgr.create_var(var)
            return h_var.out()

        #filter_size, filter_size, in_filters, out_filters

        ##[?,1,4,4], [3,3,1,16].
        self.input_after_reshape = tf.reshape(self.input, [-1, 4, 4, 1])
        self.model = ResNet(hps, self.input_after_reshape, self.label, 'train', 1, get_variable)
        self.model._build_model()
        self._loss = self.model.cost


#This holds the model symbols
class CifarModel(Model):

    def accuracy(self):
        return self.model._accuracy

    def train_op(self):
        return [self.model.train_op]

    def __init__(self, experiment, batch_provider, node_id):
        super(CifarModel, self).__init__(experiment, batch_provider, node_id)
        assert (experiment.getFlagValue('model') == 'cifar10')


        def get_variable(name,
                 shape=None,
                 dtype=None,
                 initializer=None,
                 regularizer=None,
                 trainable=True,
                 collections=None,
                 caching_device=None,
                 partitioner=None,
                 validate_shape=True,
                 custom_getter=None):

            var = tf.get_variable(name, shape, dtype, initializer, regularizer, trainable, collections, caching_device,
                            partitioner, validate_shape, custom_getter)
            h_var = self.hvar_mgr.create_var(var)
            return h_var.out()

        #filter_size, filter_size, in_filters, out_filters

        ##[?,1,4,4], [3,3,1,16].
        #self.input_after_reshape = tf.reshape(self.input, [-1, 4, 4, 1])
        hps = HParams(batch_size=None,
                      num_classes=10,
                      min_lrn_rate=0.0001,
                      lrn_rate=self.experiment.getFlagValue('lr'),
                      num_residual_units=9,
                      use_bottleneck=False,
                      weight_decay_rate=0.0002,
                      relu_leakiness=0.1,
                      optimizer=self.experiment.getFlagValue('optimizer'))

        self.model = ResNet(hps, self.input, self.label, 'train', 3, get_variable, self.hvar_mgr)
        self.model._build_model()

        #self.model._extra_train_ops.append(self.stage)
        self.model._build_train_op()

        self._loss = self.model.cost
        self.model._accuracy = self.model.accuracy #tf.group(*[self.model.accuracy, self.stage])

