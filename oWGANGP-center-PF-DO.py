#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 10 10:34:42 2018

@author: zengyang
"""
# BN for WGANGP
import tensorflow as tf
import numpy as np
#import matplotlib.pyplot as plt
import os, time, random
import math

tf.reset_default_graph()

# parameter need to be changed
cons_value = 0
lam_cons = 0
train_epoch = 1
lr_setting = 0.00002
keep_prob_train = 0.6

print('cons: %.1f lam: %.1f lr: %.5f ep: %.1f' %(cons_value, lam_cons, lr_setting, train_epoch))

# number of mesh
n_mesh = 28
n_label = 3
batch_size = 100


# generate samples
def generate_sample(n, parameter):
    ''' 
    generate samples of potential flow
    two kinds of potential flows are used : Uniform and source
    Uniform: F1(z) = V*exp(-i*alpha)*z
    source:  F2(z) = m/(2*pi)*log(z)
    x: interval of x axis
    y: interval of y axis
    n: number size of mesh
    parameter: V, alpha, m
    output: u, v the velocity of x and y direction
    '''
    # mesh
    x = [-0.5, 0.5]
    y = [-0.5, 0.5]
    x_mesh = np.linspace(x[0], x[1], int(n))
   
    y_mesh = np.linspace(y[0], y[1], int(n))
    
    X, Y = np.meshgrid(x_mesh, y_mesh)  
    U = []
    
    for i, p in enumerate(parameter):
        V = p[0]
        alpha  = p[1]
        m = p[2]
        
        # velocity of uniform
        u1 = np.ones([n, n])*V*np.cos(alpha)
        v1 = np.ones([n, n])*V*np.sin(alpha)
        
        # velocity of source
        # u2 = m/2pi * x/(x^2+y^2)
        # v2 = m/2pi * y/(x^2+y^2)
        u2 = m/(2*np.pi)*X/(X**2+Y**2)
        v2 = m/(2*np.pi)*Y/(X**2+Y**2)
        
        ur = m/(2*np.pi)/np.sqrt(X**2+Y**2)
        
        u = u1+u2
        v = v1+v2
        
        U_data = np.zeros([n, n, 2])
        U_data[:, :, 0] = u
        U_data[:, :, 1] = v
        U.append(U_data)
    return X, Y, np.asarray(U), ur

n_sam = 2000
V_mu, V_sigma = 4, 0.4
alpha_mu, alpha_sigma = 0, np.pi/20
m_mu, m_sigma = 1, 0.1

samples = np.zeros([n_sam, 3])

V_sample = np.random.normal(V_mu, V_sigma, n_sam)
alpha_sample = np.random.normal(alpha_mu, alpha_sigma, n_sam)
m_sample = np.random.normal(m_mu, m_sigma, n_sam)

samples[:,0] = V_sample
samples[:,1] = alpha_sample
samples[:,2] = m_sample

X, Y, U, ur = generate_sample(n=n_mesh, parameter=samples)

# normalization
nor_max = np.max(U)
nor_min = np.min(U)
print(nor_max)
print(nor_min)
train_set = (U-(np.max(U)+np.min(U))/2)/(1.1*(np.max(U)-np.min(U))/2)
train_label = samples

# use to calculate divergence
d_x = X[:,1:]-X[:,:-1]
d_y = Y[1:,:]-Y[:-1,:]
d_x_ = np.tile(d_x, (batch_size, 1)).reshape([batch_size, n_mesh, n_mesh-1])
d_y_ = np.tile(d_y, (batch_size, 1)).reshape([batch_size, n_mesh-1, n_mesh])

# use to filter divergence
filter = np.ones((n_mesh-1, n_mesh-1))
filter[12:15,12:15] = 0
filter_batch = np.tile(filter, (batch_size, 1)).reshape([batch_size, n_mesh-1, n_mesh-1])

#----------------------------------------------------------------------------#
#GANs
# variables : input
x = tf.placeholder(tf.float32, shape=(None, n_mesh, n_mesh, 2))
z = tf.placeholder(tf.float32, shape=(None, 1, 1, 100))
isTrain = tf.placeholder(dtype=tf.bool)
keep_prob = tf.placeholder(dtype=tf.float32, name='keep_prob')

dx = tf.placeholder(tf.float32, shape=(None, n_mesh, n_mesh-1))
dy = tf.placeholder(tf.float32, shape=(None, n_mesh-1, n_mesh))
filtertf = tf.placeholder(tf.float32, shape=(None, n_mesh-1, n_mesh-1))


def next_batch(num, labels, U):
    '''
    Return a total of `num` random samples and labels. 
    '''
    idx = np.arange(0 , len(labels))
    np.random.shuffle(idx)
    idx = idx[:num]
    
    U_shuffle = [U[i] for i in idx]
    label_shuffle = [labels[i] for i in idx]

    return np.asarray(U_shuffle), np.asarray(label_shuffle)
    
# leak_relu
def lrelu(X, leak=0.2):
    f1 = 0.5*(1+leak)
    f2 = 0.5*(1+leak)
    return f1*X+f2*tf.abs(X)

# G(z)
def generator(z, keep_prob=keep_prob, isTrain=True, reuse=False):
    with tf.variable_scope('generator', reuse=reuse):
        # initializer
        w_init = tf.truncated_normal_initializer(mean=0.0, stddev=0.02)
        b_init = tf.constant_initializer(0.0)

        # concat layer
        # z_ = np.random.normal(0, 1, (batch_size, 1, 1, 30)),
        # y_label.shape = [batch_size, 1, 1, 3]

        # 1st hidden layer
        # output.shape = (kernal.shape-1)*stride+input.shape
        # deconv1.shape = [batch_size, output.shape, **, channel]
        deconv1 = tf.layers.conv2d_transpose(z, 256, [7, 7], strides=(1, 1), padding='valid', 
                                             kernel_initializer=w_init, bias_initializer=b_init)
        lrelu1 = lrelu(tf.layers.batch_normalization(deconv1, training=isTrain), 0.2)
        lrelu1 = tf.layers.dropout(lrelu1, keep_prob)      
        
        # 2nd hidden layer
        deconv2 = tf.layers.conv2d_transpose(lrelu1, 128, [5, 5], strides=(2, 2), padding='same', 
                                             kernel_initializer=w_init, bias_initializer=b_init)
        lrelu2 = lrelu(tf.layers.batch_normalization(deconv2, training=isTrain), 0.2)
        lrelu2 = tf.layers.dropout(lrelu2, keep_prob)
        # output layer
        deconv3 = tf.layers.conv2d_transpose(lrelu2, 2, [5, 5], strides=(2, 2), padding='same', 
                                             kernel_initializer=w_init, bias_initializer=b_init)
        o = tf.nn.tanh(deconv3)

        return o

# D(x)
def discriminator(x, keep_prob=keep_prob, isTrain=True, reuse=False):
    with tf.variable_scope('discriminator', reuse=reuse):
        # initializer
        w_init = tf.truncated_normal_initializer(mean=0.0, stddev=0.02)
        b_init = tf.constant_initializer(0.0)

        # concat layer       
        #cat1 = tf.concat([x, y_fill], 3)

        # 1st hidden layer
        conv1 = tf.layers.conv2d(x, 128, [5, 5], strides=(2, 2), padding='same', kernel_initializer=w_init, bias_initializer=b_init)
        lrelu1 = lrelu(conv1, 0.2)
        lrelu1 = tf.layers.dropout(lrelu1, keep_prob)

        # 2nd hidden layer
        conv2 = tf.layers.conv2d(lrelu1, 256, [5, 5], strides=(2, 2), padding='same', kernel_initializer=w_init, bias_initializer=b_init)
        lrelu2 = lrelu(tf.layers.batch_normalization(conv2, training=isTrain), 0.2)
        lrelu2 = tf.layers.dropout(lrelu2, keep_prob)

        # output layer
        conv3 = tf.layers.conv2d(lrelu2, 1, [7, 7], strides=(1, 1), padding='valid', kernel_initializer=w_init)
        o = tf.nn.sigmoid(conv3)

        return o, conv3

def constraints(x, dx,dy, filtertf):
    # inverse normalization
    x = x*(1.1*(nor_max-nor_min)/2)+(nor_max+nor_min)/2
    '''
    This function is the constraints of potentianl flow, 
    L Phi = 0, L is the laplace calculator
    Phi is potential function
    '''
    # x.shape [batch_size, n_mesh, n_mesh, 2]
    u = tf.slice(x, [0,0,0,0], [batch_size, n_mesh, n_mesh, 1])
    v = tf.slice(x, [0,0,0,1], [batch_size, n_mesh, n_mesh, 1])
    
    u = tf.reshape(u,[batch_size, n_mesh, n_mesh])
    v = tf.reshape(v,[batch_size, n_mesh, n_mesh])
    
    u_left = tf.slice(u, [0,0,0], [batch_size, n_mesh, n_mesh-1])
    u_right = tf.slice(u, [0,0,1], [batch_size, n_mesh, n_mesh-1])
    d_u = tf.divide(tf.subtract(u_right, u_left), dx)
    
    v_up = tf.slice(v, [0,0,0], [batch_size, n_mesh-1, n_mesh])
    v_down = tf.slice(v, [0,1,0], [batch_size, n_mesh-1, n_mesh])
    d_v = tf.divide(tf.subtract(v_down, v_up), dy)
    
    delta_u = tf.slice(d_u, [0,1,0],[batch_size, n_mesh-1, n_mesh-1])
    delta_v = tf.slice(d_v, [0,0,1],[batch_size, n_mesh-1, n_mesh-1])
    
    divergence_field = delta_u+delta_v
    #filter divergence
    divergence_filter = tf.multiply(divergence_field, filtertf)
    divergence_square = tf.square(divergence_filter)
    delta = tf.reduce_mean(divergence_square,2)
    divergence_mean = tf.reduce_mean(delta, 1)
    
    # soft constraints
    kesi = tf.ones(tf.shape(divergence_mean))*(cons_value)
    delta_lose_ = divergence_mean - kesi
    delta_lose_ = tf.nn.relu(delta_lose_)
    return delta_lose_, divergence_mean

global_step = tf.Variable(0, trainable=False)
lr = tf.train.exponential_decay(lr_setting, global_step, 500, 0.95, staircase=True)

# networks : generator
G_z = generator(z,keep_prob, isTrain)

# networks : discriminator
D_real, D_real_logits = discriminator(x,keep_prob, isTrain)
D_fake, D_fake_logits = discriminator(G_z,keep_prob, isTrain, reuse=tf.AUTO_REUSE)
delta_lose, divergence_mean = constraints(G_z, dx, dy, filtertf)

# trainable variables for each network
T_vars = tf.trainable_variables()
D_vars = [var for var in T_vars if var.name.startswith('discriminator')]
G_vars = [var for var in T_vars if var.name.startswith('generator')]

lam_GP = 10

# WGAN-GP
eps = tf.random_uniform([batch_size, 1], minval=0., maxval=1.)
eps = tf.reshape(eps,[batch_size, 1, 1, 1])
eps = eps * np.ones([batch_size, n_mesh, n_mesh, 2])
X_inter = eps*x + (1. -eps)*G_z
grad = tf.gradients(discriminator(X_inter, isTrain, reuse=tf.AUTO_REUSE), [X_inter])[0]
grad_norm = tf.sqrt(tf.reduce_sum((grad)**2, axis=1))
grad_pen = lam_GP * tf.reduce_mean((grad_norm - 1)**2)

# loss for each network
D_loss_real = -tf.reduce_mean(D_real_logits)
D_loss_fake = tf.reduce_mean(D_fake_logits)
D_loss = D_loss_real + D_loss_fake + grad_pen
delta_loss = tf.reduce_mean(delta_lose)
G_loss_only = -tf.reduce_mean(D_fake_logits)
G_loss = G_loss_only + lam_cons*tf.log(delta_loss+1)


# record loss function for each network
root = './Potentialflow-results/'
if not os.path.isdir(root):
    os.mkdir(root)

# optimizer for each network 
with tf.control_dependencies(tf.get_collection(tf.GraphKeys.UPDATE_OPS)):
    optim = tf.train.AdamOptimizer(lr, beta1=0.5)
    D_optim = optim.minimize(D_loss, global_step=global_step, var_list=D_vars)
    # D_optim = tf.train.AdamOptimizer(lr, beta1=0.5).minimize(D_loss, var_list=D_vars)
    G_optim = tf.train.AdamOptimizer(lr, beta1=0.5).minimize(G_loss, var_list=G_vars)

sess = tf.InteractiveSession()
tf.global_variables_initializer().run()

train_hist = {}
train_hist['D_losses'] = []
train_hist['G_losses'] = []
train_hist['delta_real'] = []
train_hist['delta_lose'] = []
train_hist['prediction'] = []
train_hist['prediction_fit'] = []
train_hist['ratio'] = []

# save model and all variables
saver = tf.train.Saver()

# training-loop
np.random.seed(int(time.time()))
print('training start!')
start_time = time.time()

d_x_ = np.tile(d_x, (batch_size, 1)).reshape([batch_size, n_mesh, n_mesh-1])
d_y_ = np.tile(d_y, (batch_size, 1)).reshape([batch_size, n_mesh-1, n_mesh])

for epoch in range(train_epoch+1):
    G_losses = []
    D_losses = []
    delta_real_record = []
    delta_lose_record = []
    epoch_start_time = time.time()
    shuffle_idxs = random.sample(range(0, train_set.shape[0]), train_set.shape[0])
    shuffled_set = train_set[shuffle_idxs]
    shuffled_label = train_label[shuffle_idxs]
    for iter in range(shuffled_set.shape[0] // batch_size):
        # update discriminator
        x_ = shuffled_set[iter*batch_size:(iter+1)*batch_size]
        z_ = np.random.normal(0, 1, (batch_size, 1, 1, 100))
        
        loss_d_, _ = sess.run([D_loss, D_optim], {x: x_, z: z_,keep_prob:keep_prob_train, isTrain: True})
        
        # update generator
        z_ = np.random.normal(0, 1, (batch_size, 1, 1, 100))
        loss_g_, _ = sess.run([G_loss, G_optim], {z:z_, x:x_, dx:d_x_, dy:d_y_,keep_prob:keep_prob_train, filtertf:filter_batch, isTrain: True})

        errD = D_loss.eval({z:z_, x:x_, filtertf:filter_batch,keep_prob:keep_prob_train, isTrain: False})
        errG = G_loss_only.eval({z: z_, dx:d_x_, dy:d_y_,keep_prob:keep_prob_train, filtertf:filter_batch, isTrain: False})
        errdelta_real = divergence_mean.eval({z:z_, dx:d_x_, dy:d_y_,keep_prob:keep_prob_train,filtertf:filter_batch, isTrain: False})
        errdelta_lose = delta_lose.eval({z: z_, dx:d_x_, dy:d_y_, keep_prob:keep_prob_train, filtertf:filter_batch, isTrain: False})
        
        D_losses.append(errD)
        G_losses.append(errG)
        delta_real_record.append(errdelta_real)
        delta_lose_record.append(errdelta_lose)

    epoch_end_time = time.time()
    if math.isnan(np.mean(G_losses)):
        break
    per_epoch_ptime = epoch_end_time - epoch_start_time
    print('[%d/%d] - ptime: %.2f loss_d: %.3f, loss_g: %.3f, delta: %.3f' % 
          ((epoch + 1), train_epoch, per_epoch_ptime, np.mean(D_losses), np.mean(G_losses), np.mean(delta_real_record)))
    train_hist['D_losses'].append(np.mean(D_losses))
    train_hist['G_losses'].append(np.mean(G_losses))
    train_hist['delta_real'].append(np.mean(delta_real_record))
    train_hist['delta_lose'].append(np.mean(delta_lose_record))
    ### need change every time, PF: potential flow, 
    #root + 'PF-WGANGP-cons'+str(cons_value)+'-lam'+str(lam_cons)+'-lr'+str(lr_setting)+'-ep'+str(train_epoch)
    
    z_pred = np.random.normal(0, 1, (16, 1, 1, 100))
    y_label_pred = shuffled_label[0:16].reshape([16, 1, 1, n_label])
    prediction = G_z.eval({z:z_pred,keep_prob:keep_prob_train, isTrain: False})
    #prediction = prediction*np.max(U)+np.max(U)/2
    prediction = prediction*(1.1*(nor_max-nor_min)/2)+(nor_max+nor_min)/2
    train_hist['prediction'].append(prediction)
    #plot_samples(X, Y, prediction)
    #plot_samples(X, Y, prediction, name)
    if epoch % 30 == 0:
        np.random.seed(1)
        z_pred = np.random.normal(0, 1, (2000, 1, 1, 100))
        prediction = G_z.eval({z:z_pred,keep_prob:keep_prob_train, isTrain: False})
        prediction = prediction*(1.1*(nor_max-nor_min)/2)+(nor_max+nor_min)/2
        train_hist['prediction_fit'].append(prediction)

end_time = time.time()
total_ptime = end_time - start_time
name_data = root + 'PF-oWGANGP-cons'+str(cons_value)+'-lam'+str(lam_cons)+'-lr'+str(lr_setting)+'-ep'+str(train_epoch)
np.savez_compressed(name_data, a=train_hist, b=per_epoch_ptime)
save_model = name_data+'.ckpt'
save_path = saver.save(sess, save_model)