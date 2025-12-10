/**
 * Subscriptions API calls
 */

import apiClient from './client';
import { Subscription, SubscriptionTier, Usage } from '../types';

export const subscriptionsApi = {
  /**
   * Get available subscription tiers
   */
  getTiers: async (): Promise<SubscriptionTier[]> => {
    const response = await apiClient.get('/subscriptions/tiers');
    return response.data;
  },

  /**
   * Get current subscription
   */
  getCurrent: async (): Promise<Subscription> => {
    const response = await apiClient.get('/subscriptions/current');
    return response.data;
  },

  /**
   * Get usage statistics
   */
  getUsage: async (): Promise<Usage> => {
    const response = await apiClient.get('/subscriptions/usage');
    return response.data;
  },

  /**
   * Create checkout session for upgrade
   */
  createCheckout: async (data: {
    tier: 'starter' | 'pro';
    billing_period: 'monthly' | 'yearly';
    success_url: string;
    cancel_url: string;
  }): Promise<{ checkout_url: string; session_id: string }> => {
    const response = await apiClient.post('/subscriptions/checkout', data);
    return response.data;
  },

  /**
   * Create billing portal session
   */
  createPortal: async (returnUrl: string): Promise<{ portal_url: string }> => {
    const response = await apiClient.post('/subscriptions/portal', null, {
      params: { return_url: returnUrl },
    });
    return response.data;
  },

  /**
   * Cancel subscription
   */
  cancel: async (atPeriodEnd: boolean = true): Promise<{ message: string }> => {
    const response = await apiClient.post('/subscriptions/cancel', null, {
      params: { at_period_end: atPeriodEnd },
    });
    return response.data;
  },

  /**
   * Get invoices
   */
  getInvoices: async (limit: number = 10): Promise<any[]> => {
    const response = await apiClient.get('/subscriptions/invoices', {
      params: { limit },
    });
    return response.data;
  },

  /**
   * Get payment methods
   */
  getPaymentMethods: async (): Promise<any[]> => {
    const response = await apiClient.get('/subscriptions/payment-methods');
    return response.data;
  },
};

export default subscriptionsApi;
