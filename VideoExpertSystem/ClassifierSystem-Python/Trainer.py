import tensorflow as tf
from tf_scripts import retrain as tf_retrain
from sklearn.model_selection import train_test_split
from tflearn.data_utils import to_categorical
import matplotlib.pyplot as plt

import tflearn
import numpy as np
from collections import deque

import time
import os, sys, pickle
from tqdm import tqdm

import Classifier
import Categories

# Class for training CNN layer
class CNNTrainer():
    
    # Constructor
    def __init__(self, modelVersion):
        
        # Initialize as class variables
        self.tf_files_dir = "../Models/tf_files-v{0}/".format(modelVersion)
        self.dataset_dir = self.tf_files_dir + 'dataset/cnn/'
        self.modelVersion = modelVersion;
        
    # Launches the retraining process for the CNN
    def retrain(self, architecture='inception_v3', training_steps=100):
        
        # Performance metrics
        start = time.time();
        
        bottleneck_dir = self.tf_files_dir + 'bottlenecks/'
        model_dir = self.tf_files_dir + 'models/'
        summaries_dir = self.tf_files_dir + 'training_summaries/' + architecture
        output_graph_dir = self.tf_files_dir + 'retrained_graph.pb'
        output_labels_dir = self.tf_files_dir + 'retrained_labels.txt'
        
        # Very nsecure, replace with safer bridge
        os.system('python3 -m tf_scripts.retrain --bottleneck_dir=' + bottleneck_dir + ' --how_many_training_steps=' + str(training_steps) + ' --model_dir=' + model_dir + ' --sumarries_dir=' + summaries_dir + ' --output_graph=' + output_graph_dir + ' --output_labels=' + output_labels_dir + ' --architecture=' + architecture + ' --image_dir=' + self.dataset_dir);
        
        # Log time performance details
        elapsedTime = time.time() - start;
        print("Completed training process in {0:2.0f}:{1:2.0f}:{2:2.0f}!".format(elapsedTime%(3600*24)/3600, (elapsedTime%3600)/60, elapsedTime%60));
        
# Example CNN training
# trainer = CNNTrainer()
# trainer.retrain()
    
    
# Class for training RNN layer
class RNNTrainer():

    def __init__(self, labels, modelVersion):
        
        # Number of frames to consider at once
        self.FRAME_BATCH_LENGTH = 30
        
        # 2048-d vector length for image features before pooling layer from image classifier CNN 
        self.INPUT_LENGTH = 2048 
        
        # Define model version to use (tf_files-v[0.3])
        self.modelVersion = modelVersion
        
        # Initialize important directories as class variables
        self.tf_files_dir = '../../Models/tf_files-v{0}/'.format(self.modelVersion)
        self.dataset_dir = self.tf_files_dir + 'dataset/rnn/'
        self.features_dir = self.tf_files_dir + 'features/'
        self.tryCreateDirectory(self.features_dir)
        
        # Save labels to be considered
        self.labels = labels;
        
        
     # Extracts all features from pooling layer of CNN to dataset files for RNN training
    def extractPoolLayerData(self):

        # Performance monitoring
        loadStart = time.time();

        # Unpersists graph from file
        with tf.gfile.FastGFile(self.tf_files_dir + "retrained_graph.pb", 'rb') as f:
            graph_def = tf.GraphDef()
            graph_def.ParseFromString(f.read())
            _ = tf.import_graph_def(graph_def, name='')

            with tf.Session() as sess:

                # Feed the image_data as input to the graph and get pool tensor layer
                pool_tensor = sess.graph.get_tensor_by_name('pool_3:0')

                print("Loaded tensor in %.2f seconds" % (time.time() - loadStart));
                       
                # Do for all labeled categories
                for label in self.labels:
                    
                    # Generate output folder directory and create folder
                    output_folder_dir = self.features_dir + label + '/';
                    self.tryCreateDirectory(output_folder_dir);
                    
                    # Get videos within category
                    videos = os.listdir(self.dataset_dir + label)
                    
                    # Performance monitoring
                    labelStart = time.time();
                    
                    # Progress bar
                    pbar = tqdm(total=len(videos))

                    # For each video
                    for video in videos:
                    
                        # Load images (frames)
                        frames = [];
                        imagesDir = self.dataset_dir + label + '/' + video + '/'
                        imageNames = os.listdir(imagesDir);

                        # Set pool features output directory to video name
                        output_dir = output_folder_dir + video + '.dat';

                        # Skip files that aleady exists (already processed)
                        if (os.path.exists(output_dir)):
                            pbar.update(1)
                            continue

                        # Store all features in sequential array
                        cnn_features = []

                        # For every image in the video frames directory
                        for i, imageName in enumerate(imageNames):

                            # Load image data
                            image_data = tf.gfile.FastGFile(imagesDir + imageName, 'rb').read()

                            # Run CNN and extract pool tensor representation
                            try:
                                cnn_representation = sess.run(pool_tensor, {'DecodeJpeg/contents:0': image_data})
                            except KeyboardInterrupt:
                                print("Exiting... Detected CTRL+C")
                                sys.exit()
                            except:
                                print("Error making prediction, continuing..");
                                continue;

                            # Save the representation
                            frame_data = [cnn_representation, label];
                            cnn_features.append(frame_data);


                        # Save features of batch to output file
                        with open(output_dir, 'wb') as featuresOutput:
                            pickle.dump(cnn_features, featuresOutput);
                            featuresOutput.close();

                        # Update progress bar
                        pbar.update(1);

                    # Close progress bar
                    pbar.close()
                    
                    # Log label loading time
                    print (label + " processed in %d seconds!" % (time.time() - labelStart))
                        
                        
    # Get the data from our saved predictions/pooled features
    def readFeatures(self, frameBatchLength):
        
        # Performance metrics
        start = time.time();

        # X and y for dataset
        X = []
        y = []

        # Initialize featuresDeque for serving as frame features buffer
        featuresDeque = deque()
        
        # Initiate num of categories to 0
        num_categories = 0

        # Iterate through all category folders
        categories = os.listdir(self.features_dir)
        for category in self.labels:

            # Count num of categories
            num_categories += 1;

            # List video features files
            videosFeatures = os.listdir(self.features_dir + '/' + category);
            
            # Progress bar and start time for performance metrics
            pbar = tqdm(total=len(videosFeatures))
            startTime = time.time()

            # For each feature in the video batch
            for videoFeatures in videosFeatures:

                # Define full path for video features
                videoFeaturesPath = self.features_dir + '/' + category + '/' + videoFeatures
                
                # Declaration for scoping reasons
                actualLabel = "";

                # Open and get the features.
                with open(videoFeaturesPath, 'rb') as fin:
                    frameFeatures = pickle.load(fin)

                    # Enumerate and iterate through frames
                    for i, frame in enumerate(frameFeatures):
                        
                        # Only for every four frames
                        if (i % 4) == 0:          
                            
                            # Read features and label
                            cnnFeatures = frame[0]
                            actualLabel = frame[1]
                        
                            # If deque of size of batch length, start adding to X and Y
                            if (len(featuresDeque) == frameBatchLength - 1):
                                featuresDeque.append(cnnFeatures)
                                X.append(np.array(list(featuresDeque)))
                                y.append(Categories.labelToNum(actualLabel))
                                featuresDeque.popleft()
                            else:
                                # Add to the deque
                                featuresDeque.append(cnnFeatures)
                        
                        
                            
                # Update progress bar
                pbar.update(1)

            # Close progress bar and print category done message 
            pbar.close()
            
            # Calculate time for performance metrics
            timeElapsed = time.time() - startTime
            print(category + " finished in {:.2f} seconds.".format(timeElapsed))

            
        # Calculate length of the dataset
        datasetLength = len(X)
            
        # Print size of dataset
        print("Total dataset size: {}".format(datasetLength))

        # Convert to Numpy arrays
        X = np.array(X)
        y = np.array(y)

        # Reshape to dimensions, with batches of defined input length
        X = X.reshape(datasetLength, frameBatchLength, self.INPUT_LENGTH)
        
        print("X and X Shape:")
        print(X)
        print(X.shape)

        print("Y and Y Shape:")
        print(y)
        print(y.shape)
        
        # One-hot encoded categoricals.
        y = to_categorical(y, num_categories)

        # Split into train and test.
        # X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, random_state=42)

        # Log loading time
        print("Loaded data in {} seconds!".format(time.time() - start))

        # Return data
        return X, y
    
    
    # Prepare data, then train
    def autoTrain(self):
        self.extractPoolLayerData();
        self.train();
        
    # Execute training after rnn dataset is ready
    def train(self):
        
        # Log
        print("Initiating RNN training...")
        
        # Performance metrics
        start = time.time();
        
        # Training checkpoints
        CHECKPOINT_PATH = "../../Models/tf_files-v0.3/rnn-checkpoints/"
        
        # Image lookback
        frames_lookback = 16
        
        # Define training parameters
        num_epochs = 4
        total_series_length = 50000 # FIX THIS
        truncated_backprop_length = 16
        state_size = 2048
        num_classes = len(self.labels)
        echo_step = 3
        batch_size = 8
        num_batches = total_series_length//batch_size//truncated_backprop_length
        
        # Define X batch placeholder
        X_batch_ph = tf.placeholder(tf.float32, [batch_size, truncated_backprop_length, self.INPUT_LENGTH])
        
        # Y batch has batch_size elements, with categories for each backprop frame
        y_batch_ph = tf.placeholder(tf.int32, [batch_size, num_classes])
        
        # Define cell and hidden state
        cell_state_ph = tf.placeholder(tf.float32, [batch_size, state_size])
        hidden_state_ph = tf.placeholder(tf.float32, [batch_size, state_size])
        
        # Define init state for LSTM cell
        init_state = tf.nn.rnn_cell.LSTMStateTuple(cell_state_ph, hidden_state_ph)
        
        # Initialize weight variable tensors with random data
        W = tf.Variable(np.random.rand(state_size, num_classes), dtype=tf.float32)
        
        # Initialize bias variable tensors with zeroes
        b = tf.Variable(np.zeros((1, num_classes)), dtype=tf.float32)
        
        # Define input series and labels series
        inputs_series = tf.unstack(X_batch_ph, axis=1)
        labels_series = tf.unstack(y_batch_ph, axis=1)
        
        # Define LSTM cell
        cell = tf.nn.rnn_cell.BasicLSTMCell(state_size, state_is_tuple=True)
        
        # Create RNN from LSTM cell and inputs
        states_series, current_state = tf.nn.static_rnn(cell, inputs_series, init_state)

        # Define the logits fully connected layer   
        logits_series = [tf.matmul(state, W) + b for state in states_series]
        
        # Define softmax layer for one-hot encoding of output classification
        predictions_series = [tf.nn.softmax(logits) for logits in logits_series]
        
        # Define losses function
        losses = [tf.nn.sparse_softmax_cross_entropy_with_logits(logits=logits, labels=labels) for logits, labels in zip(logits_series, labels_series)]
        
        # Define total loss function
        total_loss = tf.reduce_mean(losses)
        
        # Define training step optimizer to minimize loss function
        train_step = tf.train.AdagradOptimizer(0.3).minimize(total_loss)
        
        print("Initiating TensorFlow Session...")
        
        # INITIALIZE SESSION
        with tf.Session() as sess:
            
            # Initialize all variables
            sess.run(tf.global_variables_initializer())
            
            # Graphing
            plt.ion()
            plt.figure()
            plt.show()
        
            # Define list to keep track of loss
            loss_list = []
            
            # Repeat for each epoch
            for epoch_idx in range(num_epochs):
                
                print("Loading Data for Epoch", epoch_idx)
                
                # Read the X and Y data
                x,y = self.readFeatures(truncated_backprop_length)
                
                # Calculate number of batches 
                num_batches = len(x) // batch_size
                
                # Define cell and hidden state to zeroes
                _current_cell_state = np.zeros((batch_size, state_size))
                _current_hidden_state = np.zeros((batch_size, state_size))
            
                # Batching logistics
                for batch_idx in range(num_batches):
                    
                    start_idx = batch_idx * batch_size
                    end_idx = start_idx + batch_size
                    
                    # Slice the batch
                    batchX = x[start_idx:end_idx,:,:]
                    batchY = y[start_idx:end_idx,:]
                    
                    # Run the training session
                    _total_loss, _train_step, _current_state, _predictions_series = sess.run([total_loss, train_step, current_state, predictions_series], 
                                                                                             feed_dict={
                                                                                                 X_batch_ph: batchX,
                                                                                                 y_batch_ph: batchY,
                                                                                                 cell_state_ph: _current_cell_state,
                                                                                                 hidden_state_ph: _current_hidden_state
                                                                                             })

                    # Update the current cell states
                    _current_cell_state, _current_hidden_state = _current_state

                    # Keep track of total loss by appending to local list
                    loss_list.append(_total_loss)

                    # Log training messages every 2%
                    if batch_idx % (num_batches // 50) == 0:
                        print("Step",batch_idx, "out of", num_batches,  "- Batch loss: ", _total_loss)
                        self.plotProgress(loss_list, _predictions_series, batchX, batchY, truncated_backprop_length)
                        
                print("Epoch ", epoch_idx, " completed.")
                    
        
    # Attempt to create dir
    def tryCreateDirectory(self, dir):
        try:
            os.mkdir(dir);
        except FileExistsError:
            pass        


    def plotProgress(self, loss_list, predictions_series, batchX, batchY, truncated_backprop_length):
        plt.subplot(2, 3, 1)
        plt.cla()
        plt.plot(loss_list)

        for batch_series_idx in range(5):
            
            # Transform predictions_series to a one hot encoded series
            one_hot_output_series = np.array(predictions_series)[:, batch_series_idx, :]
            single_output_series = np.array([(1 if out[0] < 0.5 else 0) for out in one_hot_output_series])

            # Create subplot
            plt.subplot(2, 3, batch_series_idx + 2)
            plt.cla()
            
            # Define plot axis [Xmin, Xmax, Ymin, Ymax]
            plt.axis([0, truncated_backprop_length, 0, 2])
            left_offset = range(truncated_backprop_length)
            
            # Compute mean for frame features in batch
            frameBatchMeans = np.array([np.mean(frame) for frame in batchX[batch_series_idx,:,:]])
            
            # Convert discrete categories to numbered
            encodedCategories = []
            for i, categoryActive in enumerate(batchY[batch_series_idx]):
                if categoryActive:
                    encodedCategories.append(i+1)
                    
            encodedCategories = np.array(encodedCategories)
            
            # encodedCategories = np.array([(Categories.NORMAL+1 if category[0] else Categories.SHOOTING+1) for category in batchY[batch_series_idx]])
            
            plt.bar(left_offset, frameBatchMeans, width=1, color="blue")
            plt.bar(left_offset, encodedCategories * 0.5, width=1, color="red")
            plt.bar(left_offset, single_output_series * 0.3, width=1, color="green")

        plt.draw()
        plt.pause(0.0001)


# Example RNN training

# Initialize trainer
trainer = RNNTrainer(['shooting', 'normal'], 0.3)
# print(trainer.readFeatures())
# Extract CNN Pool Layer Data
# trainer.extractPoolLayerData()

# Launch training process
trainer.train()



