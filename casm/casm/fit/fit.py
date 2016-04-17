import sklearn.linear_model
import sklearn.cross_validation
import sklearn.metrics
import random
import numpy as np
from math import sqrt
from casm.project import Selection, query
import casm.learn.linear_model
import casm.learn.feature_selection
import casm.learn.cross_validation
import casm.learn.tools
import os, types, json, pickle, copy

## This part needs to be in global scope for parallization #####################  
from deap import creator
from deap import base

# we'll want to minimize a cv score
creator.create("FitnessMin", base.Fitness, weights=(-1.0,))

# each individual is a list of True or False indicating if each basis function should 
# be included in the model
creator.create("Individual", list, fitness=creator.FitnessMin, input=None)
################################################################################  


def find_method(mods, attrname):
  for m in mods:
    if hasattr(m, attrname):
      return getattr(m, attrname)
  print "ERROR: Could not find a method named:", attrname
  print "Tried:", mods
  raise AttributeError("Could not find: " + attrname)


def example_input_Lasso():
  input = dict()

  # regression estimator
  input["estimator"] = dict()
  input["estimator"]["method"] = "Lasso"
  input["estimator"]["kwargs"] = dict()
  input["estimator"]["kwargs"]["alpha"] = 1e-4
  input["estimator"]["kwargs"]["max_iter"] = 1e6
  
  # feature selection
  input["feature_selection"] = dict()
  input["feature_selection"]["method"] = "SelectFromModel"
  input["feature_selection"]["kwargs"] = None
  
  # property begin fit
  input["property"] = "formation_energy"
  
  # sample weighting
  input["weight"] = dict()
  input["weight"]["method"] = "wHullDist"
  input["weight"]["kwargs"] = dict()
  input["weight"]["kwargs"]["A"] = 0.0
  input["weight"]["kwargs"]["B"] = 1.0
  input["weight"]["kwargs"]["kT"] = 0.01
  
  # cross validation
  input["cv"] = dict()
  input["cv"]["method"] = "KFold"
  input["cv"]["kwargs"] = dict()
  input["cv"]["kwargs"]["n_folds"] = 10
  input["cv"]["penalty"] = 0.0
  
  # hall of fame
  input["n_halloffame"] = 25
  
  return input

def example_input_LassoCV():
  input = dict()

  # regression estimator
  input["estimator"] = dict()
  input["estimator"]["method"] = "LassoCV"
  input["estimator"]["kwargs"] = dict()
  input["estimator"]["kwargs"]["eps"] = 1e-6
  input["estimator"]["kwargs"]["n_alphas"] = 100
  input["estimator"]["kwargs"]["max_iter"] = 1e6
  
  # feature selection
  input["feature_selection"] = dict()
  input["feature_selection"]["method"] = "SelectFromModel"
  input["feature_selection"]["kwargs"] = None
  
  # property begin fit
  input["property"] = "formation_energy"
  
  # sample weighting
  input["weight"] = dict()
  input["weight"]["method"] = "wHullDist"
  input["weight"]["kwargs"] = dict()
  input["weight"]["kwargs"]["A"] = 0.0
  input["weight"]["kwargs"]["B"] = 1.0
  input["weight"]["kwargs"]["kT"] = 0.01
  
  # cross validation
  input["cv"] = dict()
  input["cv"]["method"] = "KFold"
  input["cv"]["kwargs"] = dict()
  input["cv"]["kwargs"]["n_folds"] = 10
  input["cv"]["penalty"] = 0.0
  
  # hall of fame
  input["n_halloffame"] = 25
  
  return input

def example_input_RFE():
  input = dict()

  # regression estimator
  input["estimator"] = dict()
  input["estimator"]["method"] = "LinearRegression"
  
  # feature selection
  input["feature_selection"] = dict()
  input["feature_selection"]["method"] = "RFE"
  input["feature_selection"]["kwargs"] = dict()
  input["feature_selection"]["kwargs"]["n_features_to_select"] = 25
  
  
  # property begin fit
  input["property"] = "formation_energy"
  
  # sample weighting
  input["weight"] = dict()
  input["weight"]["method"] = "wHullDist"
  input["weight"]["kwargs"] = dict()
  input["weight"]["kwargs"]["A"] = 0.0
  input["weight"]["kwargs"]["B"] = 1.0
  input["weight"]["kwargs"]["kT"] = 0.01
  
  # cross validation
  input["cv"] = dict()
  input["cv"]["method"] = "LeaveOneOut"
  input["cv"]["penalty"] = 0.0
  
  # hall of fame
  input["n_halloffame"] = 25
  
  return input

def example_input_GeneticAlgorithm():
  input = dict()
  
  # regression estimator
  input["estimator"] = dict()
  input["estimator"]["method"] = "LinearRegression"
  
  # feature selection
  input["feature_selection"] = dict()
  input["feature_selection"]["method"] = "GeneticAlgorithm"
  d = {
    "constraints_kwargs": { 
      "Nbfunc_max": "all", 
      "Nbfunc_min": 5, 
      "FixOff": [], 
      "FixOn": []
    }, 
    "selTournamentSize": 3, 
    "mutFlipBitProb": 0.01, 
    "evolve_params_kwargs": {
      "n_generation": 10, 
      "n_repetition": 10, 
      "n_features_init": 5, 
      "n_population": 100, 
      "halloffame_filename": "ga_halloffame.pkl", 
      "n_halloffame": 50
    }, 
    "cxUniformProb": 0.5
  }
  input["feature_selection"]["kwargs"] = d
  
  
  # property begin fit
  input["property"] = "formation_energy"
  
  # sample weighting
  input["weight"] = dict()
  input["weight"]["method"] = "wHullDist"
  input["weight"]["kwargs"] = dict()
  input["weight"]["kwargs"]["A"] = 0.0
  input["weight"]["kwargs"]["B"] = 1.0
  input["weight"]["kwargs"]["kT"] = 0.01
  
  # cross validation
  input["cv"] = dict()
  input["cv"]["method"] = "LeaveOneOut"
  input["cv"]["penalty"] = 0.0
  
  # hall of fame
  input["n_halloffame"] = 25
  
  return input


def print_input_help():
  
  print \
  """
  Input files:
    Settings file: A JSON file containing settings describing how to perform the fit.
    'train': A configuration selection file used to fit the cluster expansion. 
    'population_begin.pkl': An optional input file providing an initial set of
      candidate solutions.
  
  Generated files:
    'fit_data.pkl': Stores cross validation sets, training data, model weights and
      other information that can be used when running repeatedly.
    'halloffame.pkl': Stores the best ECI sets found, as determined by the CV
      score.
    'population_end.pkl': Stores the results of the most recent optimization. Can
      be renamed 'population_begin.pkl' to use as the initial state of a new run.
  
  Settings file description:
  ------------------------------------------------------------------------------
  {
  
  # A scikit-learn linear model estimator name and keyword args used to construct  
  # the estimator object. Options include: 'LinearRegression', 'Ridge', 'Lasso', etc. 
  # See: http://scikit-learn.org/stable/modules/linear_model.html
  #
  # Note: The 'LinearRegression' estimator is implemented using 
  # casm.learn.linear_model.LinearRegressionForLOOCV', which solves X*b=y using:
  #
  #   b = np.dot(S, y)
  #   S = np.linalg.pinv(X.transpose().dot(X)).dot(X.transpose())
  #   y_pred = np.dot(H, y)
  #   H = np.dot(X, S)
  #
  # By default, the kwarg "fit_intercept" is set to False.
    "estimator": {
      "method": "LinearRegression", 
      "kwargs": null
    },
  
  # Method to use for weighting training data. 
  #
  # If weights are included, then the linear model is changed from
  #   X*b = y  ->  L*X*b = L*y, 
  #
  # where 'X' is the correlation matrix of shape (Nvalue, Nbfunc),
  # and 'property' is a vector of Nvalue calculated properties, and 
  # W = L*L.transpose() is the weight matrix.
  #
  # By default, W = np.matlib.eye(Nvalue) (unweighted).
  #
  # If the weighting method provides 1-dimensional input (this is typical), in
  # a numpy array called 'w':
  #   W = np.diag(w)*Nvalue/np.sum(w)
  #
  # If the 'custom2d' method is used, the input W_in must by Hermitian, 
  # positive-definite and is normalized by:
  #   W = W_in*Nvalue/np.sum(W_in)
  #
  # The weighting methods are:
  #   'wHullDist': Weight according to w_i = A*exp(-hull_dist/kT) + B, where A, B, 
  #     and kT are user-defined kwargs parameters, and hull_dist is the distance 
  #     from the convex hull of the training data
  #   'wEmin': Weight according to w_i = A*exp(-dist_from_minE/kT) + B,
  #     where A, B, and kT are user-defined kwargs parameters, and dist_from_minE 
  #     is calculated from the training data
  #   'wEref': weight according to w_i = A*exp(-(formation_energy - E0)/kT) + B, for
  #     (formation_energy - E0) > 0.0; and w_i = 1.0 if (formation_energy - E0) <= 0.0.
  #     where A, B, E0, and kT are user-defined kwargs parameters.
  #   'wCustom': Weights are read from a column titled 'weight' in the training data 
  #     selection file.
  #   'wCustom2d': Weights are read from columns in the training data selection file,
  #     which are expected to be titled 'weight(0)' ... 'weight(Nvalue-1)'  
    "weight": {
      "method": null, 
      "kwargs": null
    }
    
  # Name of property to be fit, as used for input to 'casm query -k'
    "property": "formation_energy", 
  
  # Hall of fame size, the number of best sets of ECI to store in 'halloffame.pkl',
  # as determined by CV score.
    "n_halloffame": 25, 
  
  # A scikit-learn cross validation method to use to generate cross validation sets.
  #
  # Options include 'KFold', 'ShuffleSplit', 'LeaveOneOut', etc.
  # See: http://scikit-learn.org/stable/modules/cross_validation.html
  #
  # The cv score reported is:
  #
  #   cv = sqrt(np.mean(scores)) + (Number of non-zero ECI)*penalty, 
  #
  # where 'scores' is an array containing the mean squared error calculated for  
  # each training/testing set, '(Number of non-zero ECI)' is the number of basis 
  # functions with non-zero ECI, and 'penalty' is the user-input penalty per basis 
  # function (default=0.0).
  #
  # Note: When the estimator is 'LinearRegression', the 'LeaveOneOut' cross-validation
  # score is calculated via:
  #
  #   LOOCV = np.mean(((y - y_pred)/(1.0 - np.diag(H)))**2)
  #   (see estimator description for definition of H) 
  #
  # By default, the kwarg "shuffle" is set to True.
    "cv": {
      "method": "LeaveOneOut", 
      "kwargs": null,
      "penalty": 0.0
    }, 
  
  # Feature selection method to use:
  #
  # Options include classes in casm.learn.feature_selection and sklearn.feature_selection:
  # Evolutionary algorithms, from casm.learn.feature_selection, are implemented
  # using deap: http://deap.readthedocs.org/en/master/index.html
  #   "GeneticAlgorithm": implements deap.algorithms.eaSimple, using selTournament,
  #     for selection, cxUniform for mating, and mutFlipBit for mutation. The
  #     probabilty of mating and mutating is set to 1.0.
  #     Options for "kwargs":
  #       "n_population": int, (default 100) Population size. This many random initial 
  #         starting individuals are created.
  #       "n_generation": int, (default 10) Number of generations between saving the hall 
  #         of fame.
  #       "n_repetition": int, (default 100) Number of repetitions of n_generation generations. 
  #         Each repetition begins with the existing final population.
  #       "n_features_init: int or "all", (default 0) Number of randomly selected 
  #          basis functions to initialize each individual with.
  #       "selTournamentSize": int, (default 3). Tournament size. A larger 
  #          tournament size weeds out less fit individuals more quickly, while
  #          a smaller tournament size weeds out less fit individuals more
  #          gradually.
  #       "cxUniformProb": number, (default 0.5) Probability of swapping bits 
  #         during mating.
  #       "mutFlipBitProb": number, (default 0.01) Probability of mutating bits
  #       "constraints": See below.
  #   "IndividualBestFirst": Best first search optimization for each individual 
  #     in the initial population. At each step, all the 'children' that differ
  #     by +/- 1 selected basis function are evaluated and the most fit child
  #     of each child is chosen to replace it's parent, until the CV score is 
  #     minimized.
  #     Options for "kwargs":
  #       "n_population": int, (default 100) Population size. This many random initial 
  #         starting individuals are minimized and the results saved in the hall 
  #         of fame.
  #       "n_generation": int, (default 10) Number of generations between saving the hall 
  #         of fame.
  #       "n_repetition": int, (default 10) Number of repetitions for minimizing n_population 
  #         individuals. Each repetition begins with a new population of random 
  #         individuals.
  #       "n_features_init: (default 5) Number of randomly selected basis functions 
  #          to initialize each individual with.
  #       "constraints": See below.
  #   "PopulationBestFirst": Each individual is associated with a 'status' that 
  #     is '1' if that individuals children have been evaluated, and '0' if they  
  #     have not been evaluated. At each step, the children of the most fit 
  #     individual with status '0' are evaluated and the population is updated to 
  #     keep only the 'n_population' most fit individuals. The algorithm stops when all 
  #     individuals in the population have status '1'.
  #       "n_population": int, (default 100) Population size. This many random initial 
  #         starting individuals are minimized and the results saved in the hall 
  #         of fame.
  #       "n_generation": int, (default 10) Number of generations between saving the hall 
  #         of fame.
  #       "n_repetition": int, (default 10) Number of repetitions for minimizing n_population 
  #         individuals. Each repetition begins with a new population of random 
  #         individuals.
  #       "n_features_init: Number of randomly selected basis functions to initialize
  #          each individual with.
  #       "constraints": See below.
  #
  # The evolutionary algorithms have an optional set of "constraints" parameters
  # that may restrict the number of basis functions selected to some range, or
  # enforce some basis functions to have or not have coefficients:
  #   "Nbfunc_min": (integer) At least Nbfunc_min basis functions must be selected at all times
  #   "Nbfunc_max": (integer or "all") No more than Nbfunc_max basis functions may be selected at 
  #     any time. Default is "all".
  #   "FixOn": An array of indices of basis functions that must be included.
  #   "FixOff": An array of indices of basis functions that may not be included.
  #
  # From sklearn.feature_selection, see: http://scikit-learn.org/stable/modules/feature_selection.html
  #   "SelectFromModel": Directly fit the chosen model using all basis functions  
  #     and select only basis functions with coefficents smaller than a "threshold"
  #     (default None). 
  #   "RFE", "RFECV": Recursive feature selection
    "feature_selection" : {
      "method": "GeneticAlgorithm",
      "kwargs": {
        "n_population": 100,
        "n_generation": 10,
        "n_repetition": 100,
        "Nbunc_init": 0,
        "selTournamentSize": 3,
        "cxUniformProb": 0.5,
        "mutFlipBitProb": 0.01,
        "constraints": {
          "Nbfunc_min": 0,
          "Nbfunc_max": "all",
          "FixOn": [],
          "FixOff": []
        }
      }
    }
  }
  ------------------------------------------------------------------------------
  """
  
  
class FittingData(object):
  """ 
  FittingData holds feature values, target values, sample weights, etc. used
  to solve:
  
    L*X * b = L*y 
  
  a weighted linear model where the weights are given by W = L * L.transpose().
    
  Attributes
  ----------
    
    X: array-like of shape (n_samples, n_features)
      The training input samples (correlations).
    
    y: array-like of shape: (n_samples, 1)
      The target values (property values).
    
    cv: cross-validation generator or an iterable
      Provides train/test splits
    
    n_samples: int
      The number of samples / target values (number of rows in X)
    
    n_features: int
      The number of features (number of columns in X)
    
    W: array-like of shape: (n_samples, n_samples)
      Contains sample weights. 
    
    L: array-like of shape: (n_samples, n_samples)
      Used to generate weighted_X and weighted_y, W = L * L.transpose(). 
    
    weighted_X: array-like of shape: (n_samples, n_features)
      Weighted training input data, weighted_X = L*x.
    
    weighted_y: array-like of shape: (n_samples, 1)
      Weighted target values, weighted_y = L*y. 
      
    scoring: string, callable or None, optional, default: None
      A string or a scorer callable object / function with signature 
      scorer(estimator, X, y). The parameter for sklearn.cross_validation.cross_val_score,
      default = None, uses estimator.score().
    
    penalty: float, optional, default=0.0
      The CV score is increased by 'penalty*(number of selected basis function)'
  """
  
  def __init__(self, X, value, cv, sample_weight=[], scoring=None, penalty=0.0):
    """
    Arguments
    ---------
    
      X: array-like of shape (n_samples, n_features)
        The training input samples (correlations).
      
      y: array-like of shape: (n_samples, 1)
        The target values (property values).
      
      cv: cross-validation generator or an iterable
        Provides train/test splits
      
      sample_weight: None, 1-d array-like of shape: (n_samples, 1), or 2-d array-like of shape: (n_samples, n_samples)
        Sample weights.
        
        if sample_weight is None: (default, unweighted)
          W = np.matlib.eye(N) 
        if sample_weight is 1-dimensional:
          W = np.diag(sample_weight)*Nvalue/np.sum(sample_weight) 
        if sample_weight is 2-dimensional (must be Hermitian, positive-definite):
          W = sample_weight*Nvalue/np.sum(sample_weight) 
      
      scoring: string, callable or None, optional, default=None
        A string or a scorer callable object / function with signature 
        scorer(estimator, X, y). The parameter for sklearn.cross_validation.cross_val_score,
        default = None, uses estimator.score().
        
      penalty: float, optional, default=0.0
        The CV score is increased by 'penalty*(number of selected basis function)'
    """
    self.X = X
    self.value = value
    
    # Number of configurations and basis functions
    self.n_samples, self.n_features = self.X.shape
    
    # weight
    self.weighted_y, self.weighted_X, self.W, self.L = casm.learn.tools.set_sample_weight(
      sample_weight, X=self.X, y=self.y)
    
    # cv sets
    self.cv = cv
    
    # scoring
    self.scoring = scoring
    
    # penalty
    self.penalty = penalty


def make_fitting_data(input, proj=None, save=True, verbose=True, read_existing=True):
  """ 
  Construct a FittingData instance, either by reading existing 'fit_data.pkl',
  or from an input settings.
  
  Arguments
  ---------
    
    input: dict
      The input settings as a dict
    
    proj: casm.project.Project, optional, default=casm.project.Project()
      A CASM project to query for training data, if input["data"]["type"] == "selection".
    
    save: boolean, optional, default=True
      Save a pickle file containing the training data and scoring metric. The file
      name, which can be specified by input["fit_data_filename"], defaults to "fit_data.pkl".
    
    verbose: boolean, optional, default=True
      Print information to stdout.
    
    read_existing: boolean, optional, default=True
      If it exists, read the pickle file containing the training data and scoring 
      metric. The file name, which can be specified by input["fit_data_filename"], 
      defaults to "fit_data.pkl".
  
  
  Returns
  -------
    
    fdata: casm.learn.FittingData
      A FittingData instance constructed based on the input parameters.
      
  """
  # set data defaults if not provided
  if "kwargs" not in input["data"] or input["data"]["kwargs"] is None:
    input["data"]["kwargs"] = dict()
  
  # set weight defaults if not provided
  sample_weight = None
  if "weight" not in input:
    input["weight"] = dict()
  if "kwargs" not in input["weight"] or input["weight"]["kwargs"] is None:
    input["weight"]["kwargs"] = dict()
  if "method" not in input["weight"]:
    input["weight"]["method"] = None
  
  # set cv kwargs and penalty (0.0) defaults
  if "kwargs" not in input["cv"] or input["cv"]["kwargs"] is None:
    input["cv"]["kwargs"] = dict()
  if "penalty" not in input["cv"]:
    input["cv"]["penalty"] = 0.0
  
  
  # property, weight, and cv inputs should remain constant
  # estimator and feature_selection might change
  fit_data_filename = input.get("fit_data_filename", "fit_data.pkl")
  
  if read_existing and os.path.exists(fit_data_filename):
    print "Reading existing fitting data from:", fit_data_filename
    fdata = pickle.load(open(fit_data_filename, 'rb'))
    print "  DONE"
    
    s = "Fitting scheme has changed.\n\n" + \
        "To proceed with the existing scheme adjust your input settings to match.\n" + \
        "To proceed with the new scheme run in a new directory or delete '" + fit_data_filename + "'."
    
    if fdata.input["property"] != input["property"]:
      print "ERROR: Input file and stored data differ. Input 'property' has changed."
      print "Stored data:\n", json.dumps(fdata.input["property"], indent=2)
      print "Input:\n", json.dumps(input["property"], indent=2)
      print s
      exit()
    
    if fdata.input["cv"] != input["cv"]:
      print "ERROR: Input file and stored data differ. Input 'cv' has changed."
      print "Stored data:\n", json.dumps(fdata.input["cv"], indent=2)
      print "Input:\n", json.dumps(input["cv"], indent=2)
      print s
      exit()
    
    if fdata.input["weight"] != input["weight"]:
      print "ERROR: Input file and stored data differ. Input 'weight' has changed."
      print "Stored data:\n", json.dumps(fdata.input["weight"], indent=2)
      print "Input:\n", json.dumps(input["weight"], indent=2)
      print s
      exit()
    
  else:
    
    ## get data ####
    
    filename = input["data"].get("filename", "train")
    data_type = input["data"].get("type", "selection").lower()
    X_name = input["data"].get("X", "corr")
    y_name = input["data"].get("y", "formation_energy")
    hull_dist_name = "hull_dist"
    
    if data_type == "selection":
        
      # read training set
      proj = casm.project.Project()
      sel = Selection(proj, filename)
      
      # get property name (required)
      property = input["data"].get("filename", "formation_energy")
      
      ## if necessary, query data
      columns = [X_name, y_name]
      if input["weight"]["method"] == "wHullDist":
        hull_dist_name = "hull_dist(" + sel.path + ",atom_frac)"
        columns.append(hull_dist_name)
      
      # perform query
      sel.query(columns)
      
      data = sel.data
      
    elif data_type.lower() == "csv":
      # populate from csv file
      data = pandas.read_csv(f, **input["data"]["kwargs"])
    
    elif data_type.lower() == "json":
      # populate from json file
      data = pandas.read_json(self.path, **input["data"]["kwargs"])
    
    # columns of interest, as numpy arrays
    X = data.loc[:,[x for x in sel.data.columns if re.match(X_name + "\([0-9]*\)", x)]].values
    y = data.loc[:,y_name].values
    if input["weight"]["method"] == "wHullDist":
      hull_dist = data.loc[:,hull_dist_name]
    
    n_samples = X.shape[0]
    n_features = X.shape[1]
    
    if verbose:
      print "# Target:", y_name
      print "# Training samples:", n_samples
      print "# Features:", n_features
    
    ## weight (optional)
    
    # get kwargs
    weight_kwargs = copy.deepcopy(input["weight"]["kwargs"])
          
    # use method to get weights
    if input["weight"]["method"] == "wCustom":
      if verbose:
        print "Reading custom weights"
      sample_weight = data["weight"].values
    elif input["weight"]["method"] == "wCustom2d":
      if verbose:
        print "Reading custom2d weights"
      cols = ["weight(" + str(i) + ")" for i in xrange(n_samples)]
      sample_weight = data.loc[:,cols].values
    elif input["weight"]["method"] == "wHullDist":
      sample_weight = casm.learn.tools.wHullDist(hull_dist, **weight_kwargs)
    elif input["weight"]["method"] == "wEmin":
      sample_weight = casm.learn.tools.wEmin(y, **weight_kwargs)
    elif input["weight"]["method"] == "wEref":
      sample_weight = casm.learn.tools.wEref(y, **weight_kwargs)
          
    if verbose:
      print "# Weighting:"
      print json.dumps(input["weight"], indent=2), "\n"
    
    
    ## cv
    cv_kwargs = copy.deepcopy(input["cv"]["kwargs"])
    
    # get cv method (required user input) and set scoring method
    # For scoring, use sklearn.metrics.mean_squared_error unless basic least 
    # squares regression is chosen, in which case use the CASM implementation
#    cv_method = None
#    if input["estimator"]["method"] == "LinearRegression" and input["cv"]["method"] == "LeaveOneOut":
#      cv_method = casm.learn.cross_validation.LeaveOneOutForLLS
#    else:
#      cv_method = find_method([sklearn.cross_validation], input["cv"]["method"])
    cv_method = find_method([sklearn.cross_validation], input["cv"]["method"])
    cv = cv_method(n_samples, **cv_kwargs)
    
    # get penalty
    penalty = input["cv"]["penalty"]
    
    if verbose:
      print "# CV:"
      print json.dumps(input["cv"], indent=2), "\n"
    
    scoring = sklearn.metrics.make_scorer(sklearn.metrics.mean_squared_error, greater_is_better=True)
#    if input["estimator"]["method"] == "LinearRegression" and input["cv"]["method"] == "LeaveOneOut":
#      scoring = None
    
    
    fdata = casm.learn.FittingData(X, y, cv, 
      sample_weight=sample_weight, scoring=scoring, penalty=penalty)
    
    fdata.input = dict()
    fdata.input["cv"] = input["cv"]
    fdata.input["weight"] = input["weight"]
    fdata.input["property"] = input["property"]
    
    if save == True:
      pickle.dump(fdata, open(fit_data_filename, 'wb'))
  
  # during runtime only, if LinearRegression and LeaveOneOut, update fdata.cv and fdata.scoring
  # to use optimized LOOCV score method
  if input["estimator"].get("method", "LinearRegression") == "LinearRegression" and input["cv"]["method"] == "LeaveOneOut":
    fdata.scoring = None
    fdata.cv = casm.learn.cross_validation.LeaveOneOutForLLS(fdata.weighted_y.shape[0])
  
  return fdata 
  

def make_estimator(input, verbose = True):
  """
  Construct estimator object from input settings.
  
  Arguments
  ---------
    
    input: dict
      The input settings as a dict
    
    verbose: boolean, optional, default=True
      Print information to stdout.
    
  
  Returns
  -------
    
    estimator:  estimator object implementing 'fit'
      The estimator specified by the input settings.
  
  """""
  
  ## estimator
  
  # get kwargs (default: fit_intercept=False)
  kwargs = copy.deepcopy(input["estimator"].get("kwargs", dict()))
  if "fit_intercept" not in kwargs:
    kwargs["fit_intercept"] = False
  
  if input["estimator"]["method"] == "LinearRegression":
    estimator_method = casm.learn.linear_model.LinearRegressionForLOOCV
  else:
    estimator_method = find_method([sklearn.linear_model], input["estimator"]["method"])
  estimator = estimator_method(**kwargs)
  
  if verbose:
    print "# Estimator:"
    print json.dumps(input["estimator"], indent=2), "\n"
    
  
  return estimator


def make_selector(input, estimator, scoring=None, cv=None, penalty=0.0, verbose=True):
  """ 
  Construct selector object from input settings
  
  Arguments
  ---------
    
    estimator:  estimator object implementing 'fit'
      The estimator specified by the input settings.
  
    scoring: string, callable or None, optional, default: None
      A string or a scorer callable object / function with signature 
      scorer(estimator, X, y). The parameter for sklearn.cross_validation.cross_val_score,
      default = None, uses estimator.score().
    
    cv: cross-validation generator or an iterable
      Provides train/test splits
    
    penalty: float, optional, default=0.0
      The CV score is increased by 'penalty*(number of selected basis function)'
    
    verbose: boolean, optional, default=True
      Print information to stdout.
    
  
  Returns
  -------
    
    selector:  selector object implementing 'fit' and having either a 
               'get_support()' or 'get_halloffame()' member
      The feature selector specified by the input settings.
    
  """
  
  # read input, construct and return a feature selector
  #
  # The feature selector should act like a sklearn.feature_selection class and
  # inherit from sklearn.base.BaseEstimator and sklearn.feature_selection.SelectorMixin,
  
  kwargs = copy.deepcopy(input["feature_selection"].get("kwargs", dict()))
  if kwargs is None:
    kwargs = dict()
  if "evolve_params_kwargs" in kwargs:
    if "halloffame_filename" not in kwargs["evolve_params_kwargs"]:
      kwargs["evolve_params_kwargs"]["halloffame_filename"] = input.get("halloffame_filename", "halloffame.pkl")
    if "n_halloffame" not in kwargs["evolve_params_kwargs"]:
      kwargs["evolve_params_kwargs"]["n_halloffame"] = input.get("n_halloffame", 25)
  
  if verbose:
    print "# Feature Selection:"
    print json.dumps(input["feature_selection"], indent=2), "\n"
  
  mods = [casm.learn.feature_selection, sklearn.feature_selection]
  
  selector_method = find_method(mods, input["feature_selection"]["method"])
  
  # check if 'cv', 'scoring', 'penalty' are allowed kwargs 
  arg_count = selector_method.__init__.func_code.co_argcount
  allowed_kwargs = selector_method.__init__.func_code.co_varnames[:arg_count]
  
  if "cv" in allowed_kwargs:
    kwargs["cv"] = cv
  if "scoring" in allowed_kwargs:
    kwargs["scoring"] = scoring
  if "penalty" in allowed_kwargs:
    kwargs["penalty"] = penalty
  
  selector = selector_method(estimator, **kwargs)
  
  return selector


def add_individual_detail(indiv, estimator, fdata, selector, input):
  """
  Adds attributes to an individual describing the details of the method used 
  calculate it and the it's prediction ability. 
  
  Adds the attributes:
  
    eci: List[(int, float)]
      A list of tuple containing the basis function index and coefficient value
      for basis functions with non-zero coefficients: [(index, coef), ...]
    
    rms: float
      The root mean square prediction error of the unweighted problem
    
    wrms: float
      The root mean square prediction error of the weighted problem
    
    estimator_method: string
      The estimator method class name
    
    feature_selection_method: string,
      The feature_selection method class name
    
    note: string
      Additional notes describing the individual
    
    input: dict
      The input settings
  
  
  Arguments
  ---------
    
    indiv: List[bool] of length n_features
      This is a boolean list of shape [n_features], in which an element is True 
      iff its corresponding feature is selected for retention.
     
    estimator:  estimator object implementing 'fit'
      The estimator specified by the input settings.
    
    fdata: casm.learn.FittingData
      A FittingData instance containing the problem data.
    
    selector:  selector object implementing 'fit' and having either a 
               'get_support()' or 'get_halloffame()' member
      The feature selector specified by the input settings.
    
    input: dict
      The input settings
  
    
  Note
  ----
    Individuals should already have a 'fitness.values' attribute with the cv
    score. As is the convention in the 'deap' package, the 'fitness.values' 
    attribute is a tuple with the first element being the cv score.
    
  """
  # eci
  estimator.fit(fdata.weighted_X[:,casm.learn.tools.indices(indiv)], fdata.weighted_y)
  indiv.eci = casm.learn.tools.eci(indiv, estimator.coef_)
  
  # rms and wrms
  indiv.rms = sqrt(sklearn.metrics.mean_squared_error(
    fdata.value, estimator.predict(fdata.X[:,casm.learn.tools.indices(indiv)])))
  indiv.wrms = sqrt(sklearn.metrics.mean_squared_error(
    fdata.weighted_y, estimator.predict(fdata.weighted_X[:,casm.learn.tools.indices(indiv)])))
  
  # estimator (hide implementation detail)
  indiv.estimator_method = type(estimator).__name__
  if indiv.estimator_method == "LinearRegressionForLOOCV":
    indiv.estimator_method = "LinearRegression"
  
  # feature_selection
  indiv.feature_selection_method = type(selector).__name__
  
  # note
  indiv.note = input.get("note", "")
  
  # input settings
  indiv.input = input
  
  return indiv


def print_population(pop):
  """ 
  Print all individual in a population.
  
  Example:
    
    Index: Selected                                    #Selected    CV           
    ----------------------------------------------------------------------------------------------------
        0: 0111011110000111000001001100000100010000... 25           0.015609282  
        1: 0111011110000111000001001101000100010000... 25           0.015611913  
        2: 0111011110000111000001001100000100010000... 24           0.015619745  
    ...
  
  
  Arguments
  ---------
    
    pop: List-like of List[bool] of length n_features
      A population, a list-like container of individuals. Each individual is a 
      boolean list of shape [n_features], in which an element is True iff its 
      corresponding feature is selected for retention.
  """
  print "{0:5}: {1:43} {2:<12} {3:<12}".format("Index", "Selected", "#Selected", "CV")
  print "-"*100
  form_str = "{0:5}: {1} {2:<12} {3:<12.8g}"
  for i in range(len(pop)):
    bitstr = ""
    for j in range(min(len(pop[i]),40)):
      if pop[i][j]:
        bitstr += '1'
      else:
        bitstr += '0'
    if len(pop[i]) > 40:
      bitstr += "..."  
    print form_str.format(i, bitstr, sum(pop[i]), pop[i].fitness.values[0])


def to_json(index, indiv):
  """
  Serialize an individual to JSON. 
  
  
  Arguments
  ---------
    
    index: int
      The index in hall of fame of the individual
      
    indiv: List[bool] of length n_features
      This is a boolean list of shape [n_features], in which an element is True 
      iff its corresponding feature is selected for retention.
  
  
  Note
  ----
  
    ECI are serialized using cls=casm.NoIndent, so when writing with json.dump or 
    json.dumps, include 'cls=casm.NoIndentEncoder'.
  
  """
  d = dict()
  bitstr = ""
  for j in xrange(len(indiv)):
    if indiv[j]:
      bitstr += '1'
    else:
      bitstr += '0'
  d["selected"] = bitstr
  d["index"] = index
  d["n_selected"] = sum(indiv)
  d["cv"] = indiv.fitness.values[0]
  d["rms"] = indiv.rms
  d["wrms"] = indiv.wrms
  d["estimator_method"] = indiv.estimator_method
  d["feature_selection_method"] = indiv.feature_selection_method
  d["note"] = indiv.note
  d["eci"] = []
  for bfunc in indiv.eci:
    d["eci"].append(casm.NoIndent(bfunc))
  d["input"] = indiv.input
  return d


def _print_individual(index, indiv, format=None):
  """ 
  Print all individual in hall of fame.
  
  Index: Selected                                    #Selected    CV          wRMS        
  ----------------------------------------------------------------------------------------------------
      0: 0111011110000111000001001100000100010000... 25           0.015609282  0.014073401 
      1: 0111011110000111000001001101000100010000... 25           0.015611913  0.014045382 
      2: 0111011110000111000001001100000100010000... 24           0.015619745  0.01411583  
  ...
  """
  if format is None:
    if len(indiv) > 40:
      bitstr_len = 43
    else:
      bitstr_len = len(indiv)
    form_str = "{0:5}: {1:<" + str(bitstr_len) + "} {2:<12} {3:<12.8g} {4:<12.8g} {5:<12.8g} {6:<24} {7:<24} {8}"
    bitstr = ""
    for j in range(min(len(indiv),40)):
      if indiv[j]:
        bitstr += '1'
      else:
        bitstr += '0'
    if len(indiv) > 40:
      bitstr += "..."  
    print form_str.format(index, bitstr, sum(indiv), indiv.fitness.values[0], 
      indiv.rms, indiv.wrms, indiv.estimator_method, indiv.feature_selection_method, indiv.note)
    return
    
  elif format.lower() == "json":
    print json.dumps(to_json(index,indiv), indent=2, cls=casm.NoIndentEncoder)
    return
    
  elif format.lower() == "details":
    print "##"
    print "Index:", index
    
    bitstr = ""
    for j in xrange(len(indiv)):
      if indiv[j]:
        bitstr += '1'
      else:
        bitstr += '0'
    print "Selected:", bitstr
    print "#Selected:", sum(indiv)
    print "CV:", indiv.fitness.values[0]
    print "RMS:", indiv.rms
    print "wRMS:", indiv.wrms
    print "Estimator:", indiv.estimator_method
    print "FeatureSelection:", indiv.feature_selection_method
    print "Note:", indiv.note
    print "ECI:\n"
    print_eci(indiv.eci)
    print "Input:\n", json.dumps(indiv.input, indent=2)
    return


def _print_halloffame_header(hall):
  """ 
  Print header for hall of fame.
  """
  if len(hall[0]) > 40:
    bitstr_len = 43
  else:
    bitstr_len = len(hall[0])
  print ("{0:5}: {1:<" + str(bitstr_len) + "} {2:<12} {3:<12} {4:<12} {5:<12} {6:<24} {7:<24} {8}").format(
    "Index", "Selected", "#Selected", "CV", "RMS", "wRMS", "Estimator", "FeatureSelection", "Note")
  print "-"*(6+bitstr_len+13*4+25*3)


def print_individual(hall, indices, format=None):
  """ 
  Print selected individuals from hall of fame.
  
  Arguments:
  ----------
  
    hall: deap.tools.HallOfFame
      A Hall Of Fame of ECI sets
    
    index: List[int]
      Indices of individual in hall to be printed
    
    format: str, optional, default=None
      Options: 
        None:      to print summary only
        "details": to print more
        "json":    to print as JSON  
  """
  if format is None:
    _print_halloffame_header(hall)
    for index in indices:
      _print_individual(index, hall[index], format=format)
    return
    
  elif format.lower() == "json":
    h = []
    for index in indices:
      d = to_json(index, hall[index])
      h.append(d)
    print json.dumps(h, indent=2, cls=casm.NoIndentEncoder)
      
    
  elif format.lower() == "details":
    for index in indices:
      _print_individual(index, hall[index], format=format)
    print ""
  return

def print_halloffame(hall, format=None):
  """ 
  Print all individual in hall of fame.
  
  Arguments:
  ----------
  
    hall: deap.tools.HallOfFame
      A Hall Of Fame of ECI sets
    
    format: str, optional, default=None
      Options: 
        None:      to print summary only
        "details": to print more
        "json":    to print as JSON 
  """
  if format is None:
    _print_halloffame_header(hall)
    for index, indiv in enumerate(hall):
      _print_individual(index, indiv, format=format)
      
    return
    
  elif format.lower() == "json":
    h = []
    for index, indiv in enumerate(hall):
      d = to_json(index, indiv)
      h.append(d)
    print json.dumps(h, indent=2, cls=casm.NoIndentEncoder)
      
    
  elif format.lower() == "details":
    for index, indiv in enumerate(hall):
      _print_individual(index, indiv, format=format)
      print ""
    
    return


def print_eci(eci):
  """
  Print ECI.
  
  Format:
      1: -1.53460558686
      2:  0.574571156376
      3:  1.04379783648
  ...
  
  Arguments
  ---------
    
    eci: List[(int, float)]
      A list of tuple containing the basis function index and coefficient value
      for basis functions with non-zero coefficients: [(index, coef), ...]
  
  """
  for bfunc in eci:
    print "{index:>5}: {value:< .12g}".format(index=bfunc[0], value=bfunc[1])




