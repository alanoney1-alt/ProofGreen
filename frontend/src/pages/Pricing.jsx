import { useState, useEffect } from 'react'
import { subscriptionsAPI } from '../services/api'
import toast from 'react-hot-toast'
import { CheckIcon } from '@heroicons/react/24/outline'

export default function Pricing() {
  const [plans, setPlans] = useState([])
  const [currentSubscription, setCurrentSubscription] = useState(null)
  const [usage, setUsage] = useState(null)
  const [loading, setLoading] = useState(true)
  const [billingCycle, setBillingCycle] = useState('monthly')
  const [upgrading, setUpgrading] = useState(false)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [plansRes, subRes] = await Promise.all([
        subscriptionsAPI.getPlans(),
        subscriptionsAPI.getCurrent()
      ])
      setPlans(plansRes.data.plans)
      setCurrentSubscription(subRes.data.subscription)
      setUsage(subRes.data.usage)
    } catch (error) {
      console.error('Failed to fetch pricing data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleUpgrade = async (planId) => {
    setUpgrading(true)
    try {
      await subscriptionsAPI.upgrade({ planId, billingCycle })
      toast.success('Subscription updated!')
      fetchData()
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to upgrade')
    } finally {
      setUpgrading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  const currentPlanId = currentSubscription?.pricing_plans?.id

  return (
    <div className="animate-fade-in">
      <div className="text-center mb-12">
        <h1 className="text-3xl font-bold text-gray-900">Pricing Plans</h1>
        <p className="text-gray-600 mt-2">
          Choose the plan that fits your business
        </p>

        {/* Billing Toggle */}
        <div className="mt-6 inline-flex items-center p-1 bg-gray-100 rounded-lg">
          <button
            onClick={() => setBillingCycle('monthly')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              billingCycle === 'monthly'
                ? 'bg-white text-gray-900 shadow'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Monthly
          </button>
          <button
            onClick={() => setBillingCycle('yearly')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              billingCycle === 'yearly'
                ? 'bg-white text-gray-900 shadow'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Yearly (Save 20%)
          </button>
        </div>
      </div>

      {/* Current Usage */}
      {usage && currentSubscription && (
        <div className="card p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Current Usage</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-600">Jobs this month</span>
                <span className="font-medium">
                  {usage.jobs.used} / {usage.jobs.limit || 'Unlimited'}
                </span>
              </div>
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${usage.jobs.percentage > 80 ? 'bg-yellow-500' : 'bg-primary-500'}`}
                  style={{ width: `${Math.min(usage.jobs.percentage, 100)}%` }}
                />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-600">Team members</span>
                <span className="font-medium">
                  {usage.users.used} / {usage.users.limit || 'Unlimited'}
                </span>
              </div>
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${usage.users.percentage > 80 ? 'bg-yellow-500' : 'bg-primary-500'}`}
                  style={{ width: `${Math.min(usage.users.percentage, 100)}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Plans Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
        {plans.map((plan) => {
          const isCurrentPlan = currentPlanId === plan.id
          const price = billingCycle === 'yearly'
            ? (plan.price_yearly / 12).toFixed(0)
            : plan.price_monthly

          return (
            <div
              key={plan.id}
              className={`card p-6 relative ${
                isCurrentPlan ? 'ring-2 ring-primary-500' : ''
              } ${plan.slug === 'professional' ? 'border-primary-200 bg-primary-50/30' : ''}`}
            >
              {plan.slug === 'professional' && (
                <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                  <span className="badge badge-green">Most Popular</span>
                </div>
              )}

              {isCurrentPlan && (
                <div className="absolute -top-3 right-4">
                  <span className="badge badge-blue">Current Plan</span>
                </div>
              )}

              <div className="text-center mb-6">
                <h3 className="text-xl font-bold text-gray-900">{plan.name}</h3>
                <div className="mt-4">
                  <span className="text-4xl font-bold text-gray-900">${price}</span>
                  <span className="text-gray-500">/mo</span>
                </div>
                {billingCycle === 'yearly' && (
                  <p className="text-sm text-green-600 mt-1">
                    ${plan.price_yearly}/year
                  </p>
                )}
              </div>

              <ul className="space-y-3 mb-6">
                <li className="flex items-center text-sm">
                  <CheckIcon className="w-5 h-5 text-green-500 mr-2 flex-shrink-0" />
                  <span>{plan.job_limit ? `${plan.job_limit} jobs/month` : 'Unlimited jobs'}</span>
                </li>
                <li className="flex items-center text-sm">
                  <CheckIcon className="w-5 h-5 text-green-500 mr-2 flex-shrink-0" />
                  <span>{plan.user_limit ? `${plan.user_limit} team members` : 'Unlimited users'}</span>
                </li>
                <li className="flex items-center text-sm">
                  <CheckIcon className="w-5 h-5 text-green-500 mr-2 flex-shrink-0" />
                  <span>{plan.ai_analysis_limit ? `${plan.ai_analysis_limit} AI analyses/mo` : 'Unlimited AI'}</span>
                </li>
                {plan.features?.map((feature, i) => (
                  <li key={i} className="flex items-center text-sm">
                    <CheckIcon className="w-5 h-5 text-green-500 mr-2 flex-shrink-0" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>

              <button
                onClick={() => handleUpgrade(plan.id)}
                disabled={isCurrentPlan || upgrading}
                className={`w-full py-2 px-4 rounded-lg font-medium transition-colors ${
                  isCurrentPlan
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : plan.slug === 'professional'
                    ? 'bg-primary-600 text-white hover:bg-primary-700'
                    : 'bg-gray-900 text-white hover:bg-gray-800'
                }`}
              >
                {isCurrentPlan ? 'Current Plan' : 'Select Plan'}
              </button>
            </div>
          )
        })}
      </div>

      {/* FAQ */}
      <div className="mt-16 max-w-3xl mx-auto">
        <h2 className="text-2xl font-bold text-gray-900 text-center mb-8">
          Frequently Asked Questions
        </h2>
        <div className="space-y-6">
          <div className="card p-6">
            <h3 className="font-semibold text-gray-900">What happens if I exceed my limits?</h3>
            <p className="text-gray-600 mt-2">
              You'll receive a notification when approaching your limits. You can upgrade at any time to continue using the platform without interruption.
            </p>
          </div>
          <div className="card p-6">
            <h3 className="font-semibold text-gray-900">Can I cancel anytime?</h3>
            <p className="text-gray-600 mt-2">
              Yes, you can cancel your subscription at any time. You'll retain access until the end of your billing period.
            </p>
          </div>
          <div className="card p-6">
            <h3 className="font-semibold text-gray-900">Is there a free trial?</h3>
            <p className="text-gray-600 mt-2">
              All new accounts start with a 14-day free trial of the Founders plan. No credit card required.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
