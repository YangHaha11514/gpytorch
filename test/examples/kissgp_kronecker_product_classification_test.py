import math
import torch
import gpytorch
from torch import nn, optim
from torch.autograd import Variable
from gpytorch.kernels import RBFKernel, GridInterpolationKernel
from gpytorch.means import ConstantMean
from gpytorch.likelihoods import BernoulliLikelihood
from gpytorch.random_variables import GaussianRandomVariable
from gpytorch.inference import Inference

train_x = torch.zeros(16, 2)
train_y = torch.zeros(16)
for i in range(4):
    for j in range(4):
        train_x[i * 4 + j][0] = i
        train_x[i * 4 + j][1] = j
        train_y[i * 4 + j] = pow(-1, int(i / 2) + int(j / 2))
train_x = Variable(train_x)
train_y = Variable(train_y)


class GPClassificationModel(gpytorch.GPModel):
    def __init__(self):
        super(GPClassificationModel, self).__init__(BernoulliLikelihood())
        self.mean_module = ConstantMean(constant_bounds=[-1e-5, 1e-5])
        self.covar_module = RBFKernel(log_lengthscale_bounds=(-5, 6))
        self.grid_covar_module = GridInterpolationKernel(self.covar_module)
        self.register_parameter('log_outputscale', nn.Parameter(torch.Tensor([0])), bounds=(-5, 6))
        self.initialize_interpolation_grid(10, grid_bounds=[(0, 3), (0, 3)])

    def forward(self, x):
        mean_x = self.mean_module(x)
        covar_x = self.grid_covar_module(x)
        covar_x = covar_x.mul(self.log_outputscale.exp())
        latent_pred = GaussianRandomVariable(mean_x, covar_x)
        return latent_pred


def test_kissgp_classification_error():
    prior_model = GPClassificationModel()

    infer = Inference(prior_model)
    posterior_model = infer.run(train_x, train_y)

    # Find optimal model hyperparameters
    posterior_model.train()
    optimizer = optim.Adam(posterior_model.parameters(), lr=0.15)
    optimizer.n_iter = 0
    for i in range(200):
        optimizer.zero_grad()
        output = posterior_model.forward(train_x)
        loss = -posterior_model.marginal_log_likelihood(output, train_y)
        loss.backward()
        optimizer.n_iter += 1
        optimizer.step()

    # Set back to eval mode
    posterior_model.eval()
    test_preds = posterior_model(train_x).mean().ge(0.5).float().mul(2).sub(1).squeeze()
    mean_abs_error = torch.mean(torch.abs(train_y - test_preds) / 2)
    assert(mean_abs_error.data.squeeze()[0] < 1e-5)
