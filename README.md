## Currently the repository supports deployment and setup of django projects on linux based hosts

* To use  clone the repo using git  and create a file `config.yaml` using the `config.yaml.sample`
* Add your prouduction and stating .env files to `production-envs` and `staging-envs` S3 buckets respectively
* run `fab prod setup` or `fab staging setup` to setup the environments on hosts defined in `config.yaml`
* run `fab prod deploy` to  deploy the current master branch 
* run `fab prod deploy --branch  <tag/branch>` to deploy the respective tag/branch 
* run `fab prod rollback` to rollback to current deployment to previous release
* run `fab prod rollback --version <version>` to rollback to specified version (supports 1,2 and 3)

### Note ### 
* By default currently last 3 releases are saved on hosts and hence rollback is support for last 3 deployments
* This repo uses the concept of atomic deployments for zero downtime deployment.
Read more about this [here](https://buddy.works/blog/introducing-atomic-deployments)

* Do try deployments using this repo and create an issue in case something is not working

*Pull requests for feature enhancement are welcome* 

