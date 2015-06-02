.. code::

 clouds:
   cloudwatt:
     auth:
       auth_url: https://identity.fr1.cloudwatt.com/v2.0
       username: user@domain.tld
       password: password
       project_name: COMPUTE-xyz
     region_name: fr1

.. code::

 phoobe --os-cloud-config-name cloudwatt --environment-file samples/cloudwatt/environment.yaml up

.. code::

 phoobe --os-cloud-config-name cloudwatt --environment-file samples/cloudwatt/environment.yaml resources

.. code::

 phoobe --os-cloud-config-name cloudwatt --environment-file samples/cloudwatt/environment.yaml provision

.. code::

 phoobe --os-cloud-config-name cloudwatt --environment-file samples/cloudwatt/environment.yaml ssh

.. code::

 phoobe --os-cloud-config-name cloudwatt --environment-file samples/cloudwatt/environment.yaml destroy
