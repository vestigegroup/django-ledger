from django.contrib import messages
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import ArchiveIndexView, CreateView, DetailView, UpdateView

from django_ledger.forms.customer_job import (CustomerJobModelCreateForm, CustomerJobModelUpdateForm,
                                              CustomerJobItemFormset)
from django_ledger.models import EntityModel, ItemThroughModel
from django_ledger.models.customer_job import CustomerJobModel
from django_ledger.views import LoginRequiredMixIn


class CustomerJobModelListView(LoginRequiredMixIn, ArchiveIndexView):
    template_name = 'django_ledger/customer_job/customer_job_list.html'
    context_object_name = 'customer_job_list'
    PAGE_TITLE = _('Customer Jobs')
    date_field = 'created'
    paginate_by = 20
    paginate_orphans = 2
    allow_empty = True
    extra_context = {
        'page_title': PAGE_TITLE,
        'header_title': PAGE_TITLE,
        'header_subtitle_icon': 'eos-icons:job'
    }

    def get_queryset(self):
        return CustomerJobModel.objects.for_entity(
            entity_slug=self.kwargs['entity_slug'],
            user_model=self.request.user
        ).select_related('customer')

    def get_date_field(self):
        return 'created'


class CustomerJobModelCreateView(LoginRequiredMixIn, CreateView):
    PAGE_TITLE = _('Create Customer Job')
    extra_context = {
        'page_title': PAGE_TITLE,
        'header_title': PAGE_TITLE,
        'header_subtitle_icon': 'eos-icons:job'
    }
    template_name = 'django_ledger/customer_job/customer_job_create.html'

    def get_form_class(self):
        return CustomerJobModelCreateForm

    def get_form(self, form_class=None):
        form_class = self.get_form_class()
        return form_class(entity_slug=self.kwargs['entity_slug'],
                          user_model=self.request.user,
                          **self.get_form_kwargs())

    def get_success_url(self):
        cj_model: CustomerJobModel = self.object
        return reverse('django_ledger:customer-job-detail',
                       kwargs={
                           'entity_slug': self.kwargs['entity_slug'],
                           'customer_job_pk': cj_model.uuid
                       })

    def form_valid(self, form):
        cj_model: CustomerJobModel = form.save(commit=False)

        # making sure the user as permissions on entity_model...
        entity_model_qs = EntityModel.objects.for_user(user_model=self.request.user).only('uuid')
        entity_model: EntityModel = get_object_or_404(entity_model_qs, slug=self.kwargs['entity_slug'])
        cj_model.entity = entity_model

        return super(CustomerJobModelCreateView, self).form_valid(form)


class CustomerJobModelDetailView(LoginRequiredMixIn, DetailView):
    pk_url_kwarg = 'customer_job_pk'
    template_name = 'django_ledger/customer_job/customer_job_detail.html'
    PAGE_TITLE = _('Customer Job Detail')
    context_object_name = 'customer_job'
    extra_context = {
        'hide_menu': True
    }

    def get_context_data(self, **kwargs):
        context = super(CustomerJobModelDetailView, self).get_context_data(**kwargs)
        cj_model: CustomerJobModel = self.object
        context['page_title'] = self.PAGE_TITLE,
        context['header_title'] = self.PAGE_TITLE
        context['header_subtitle'] = cj_model.title
        context['header_subtitle_icon'] = 'eos-icons:job'
        context['customer_job_item_list'] = cj_model.itemthroughmodel_set.all()
        return context

    def get_queryset(self):
        return CustomerJobModel.objects.for_entity(
            entity_slug=self.kwargs['entity_slug'],
            user_model=self.request.user
        ).select_related('customer')


class CustomerJobModelUpdateView(LoginRequiredMixIn, UpdateView):
    template_name = 'django_ledger/customer_job/customer_job_update.html'
    pk_url_kwarg = 'customer_job_pk'
    context_object_name = 'customer_job'
    PAGE_TITLE = _('Customer Job Update')
    http_method_names = ['get', 'post']

    action_update_items = False

    def get_form_class(self):
        return CustomerJobModelUpdateForm

    def get_form(self, form_class=None):
        form_class = self.get_form_class()
        return form_class(
            **self.get_form_kwargs()
        )

    # def get_item_through_queryset(self):
    #     bill_model: CustomerJobModel = self.object
    #     if not self.item_through_qs:
    #         self.item_through_qs = bill_model.itemthroughmodel_set.select_related(
    #             'item_model', 'po_model', 'bill_model').order_by('-total_amount')
    #     return self.item_through_qs

    def get_context_data(self, item_formset: CustomerJobItemFormset = None, **kwargs):
        context = super(CustomerJobModelUpdateView, self).get_context_data(**kwargs)
        cj_model: CustomerJobModel = self.object
        context['page_title'] = self.PAGE_TITLE,
        context['header_title'] = self.PAGE_TITLE
        context['header_subtitle'] = cj_model.title
        context['header_subtitle_icon'] = 'eos-icons:job'

        if not item_formset:
            item_through_qs, aggregate_data = cj_model.get_itemthrough_data()
            item_formset = CustomerJobItemFormset(
                entity_slug=self.kwargs['entity_slug'],
                user_model=self.request.user,
                customer_job_model=cj_model,
                queryset=item_through_qs)
        else:
            item_through_qs: ItemThroughModel = item_formset.queryset

        context['customer_job_item_list'] = item_through_qs
        context['revenue_estimate'] = aggregate_data['revenue_estimate']
        context['cost_estimate'] = aggregate_data['cost_estimate']
        context['cj_formset'] = item_formset
        return context

    def get_queryset(self):
        return CustomerJobModel.objects.for_entity(
            entity_slug=self.kwargs['entity_slug'],
            user_model=self.request.user
        ).select_related('customer')

    def get_success_url(self):
        return reverse('django_ledger:customer-job-detail',
                       kwargs={
                           'entity_slug': self.kwargs['entity_slug'],
                           'customer_job_pk': self.kwargs['customer_job_pk']
                       })

    def get(self, request, entity_slug, customer_job_pk, *args, **kwargs):

        # this action can only be used via POST request...
        if self.action_update_items:
            return HttpResponseBadRequest()

        return super(CustomerJobModelUpdateView, self).get(request, *args, **kwargs)

    def post(self, request, entity_slug, customer_job_pk, *args, **kwargs):

        response = super(CustomerJobModelUpdateView, self).post(request, *args, **kwargs)
        cj_model: CustomerJobModel = self.get_object()

        # this action can only be used via POST request...
        if self.action_update_items:
            item_formset: CustomerJobItemFormset = CustomerJobItemFormset(request.POST,
                                                                          user_model=self.request.user,
                                                                          customer_job_model=cj_model,
                                                                          entity_slug=entity_slug)
            if item_formset.is_valid():
                if item_formset.has_changed():
                    cleaned_data = [d for d in item_formset.cleaned_data if d]
                    cj_items = item_formset.save(commit=False)
                    cj_model_qs = CustomerJobModel.objects.for_entity(user_model=self.request.user,
                                                                      entity_slug=entity_slug)
                    cj_model: CustomerJobModel = get_object_or_404(cj_model_qs, uuid__exact=customer_job_pk)
                    entity_qs = EntityModel.objects.for_user(user_model=self.request.user)
                    entity_model: EntityModel = get_object_or_404(entity_qs, slug__exact=entity_slug)

                    for item in cj_items:
                        item.entity = entity_model
                        item.cjob_model = cj_model

                    item_formset.save()

                    cj_model.update_state()
                    cj_model.clean()
                    cj_model.save(update_fields=[
                        'revenue_estimate',
                        'labor_estimate',
                        'equipment_estimate',
                        'material_estimate',
                        'updated'
                    ])

                    messages.add_message(request,
                                         message=f'Customer Job items saved.',
                                         level=messages.SUCCESS,
                                         extra_tags='is-success')

                    return HttpResponseRedirect(reverse('django_ledger:customer-job-update',
                                                        kwargs={
                                                            'entity_slug': entity_slug,
                                                            'customer_job_pk': customer_job_pk
                                                        }))


            else:
                context = self.get_context_data(item_formset=item_formset)
                return self.render_to_response(context=context)

        return response