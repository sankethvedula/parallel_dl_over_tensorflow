


import pickle
import os

import utils

#Manage the whereabout of the data of the experiments

class ExperimentsManager(object):
    __metaclass__ = utils.Singleton

    BASE_PATH = '/home/shai/ExperimentsManager/'
    METADATA_FILE = BASE_PATH + 'metadata'
    TENSOR_BOARD_DIRS = BASE_PATH + 'TensorBoard/'
    MODEL_CHECKPOINT_DIRS = BASE_PATH + 'ModelCheckpoints/'


    def __init__(self):
        #self.running = None
        #self.metadata is a dict from Experiment to path under BASE_PATH.
        self.curr_experiment = None
        if not os.path.exists(os.path.dirname(ExperimentsManager.METADATA_FILE)):
            try:
                os.makedirs(os.path.dirname(ExperimentsManager.METADATA_FILE))
            except os.OSError as exc:  # Guard against race condition
                if exc.errno != os.errno.EEXIST:
                    raise

        self.metadata = {}
        self.refresh_metadata()

    #private

    #in case another process added experiments and took away free indexes!
    def refresh_metadata(self):
        try:
            with open(ExperimentsManager.METADATA_FILE, 'rb') as f:
                loaded_metadata = pickle.load(f)
                self.metadata.update(loaded_metadata)
        except:
            raise
            print ExperimentsManager.METADATA_FILE + ' does not exist yet, programmer should uncomment the line that creates it'
            self.dunp_metadata()
            try:
                with open(ExperimentsManager.METADATA_FILE, 'rb') as f:
                    self.metadata.update(pickle.load(f))
            except:
                assert(False)



    def dunp_metadata(self):
        with open(ExperimentsManager.METADATA_FILE, 'wb') as f:
            pickle.dump(self.metadata, f)

    def find_free_index(self):
        if len(self.metadata.values()) == 0:
            return 0

        return max(self.metadata.values()) + 1

    def lookup_experiment_path(self, experiment):
        if experiment not in self.metadata:
            return None
        return ExperimentsManager.BASE_PATH + str(self.metadata[experiment])

    #params is a dictionary from flag names to values
    def allocate_experiment(self, experiment):
        print '############### New experiment allocating path ################'

        #assert that the experiment does not exists yet
        assert(self.lookup_experiment_path(experiment) == None)
        self.metadata[experiment] = self.find_free_index()
        self.dunp_metadata()

        print self.lookup_experiment_path(experiment)
        return self.lookup_experiment_path(experiment)


    ######################   API   ############################:
    @classmethod
    def get(cls):
        return ExperimentsManager()


    def get_experiment_model_tensorboard_dir(self, experiment, model_idx):
        self.dump_experiment(experiment)
        return ExperimentsManager.TENSOR_BOARD_DIRS + str(self.metadata[experiment]) + '/model_' + str(model_idx)

    def get_experiment_model_checkpoint_dir(self, experiment, model_idx):
        return ExperimentsManager.MODEL_CHECKPOINT_DIRS + str(self.metadata[experiment]) + '/model_' + str(model_idx)

    def dump_experiment(self, experiment):

        path = self.lookup_experiment_path(experiment)
        if path == None:
            path = self.allocate_experiment(experiment)

        utils.printInfo('Dumping into ' + str(path))
        with open(path, 'wb') as f:
            return pickle.dump(experiment, f)

        #TODO: add dump model weights

    def load_experiment(self, experiment):
        print 'experiment = ' + str(experiment)
        path = self.lookup_experiment_path(experiment)
        if path is None:
            #assert(False)
            return None

        utils.printInfo( 'Loading from ' + str(path))
        with open(path, 'rb') as f:
            res = pickle.load(f)
            #experiment.results = res.results

            # TODO: add load model weights

            return res






