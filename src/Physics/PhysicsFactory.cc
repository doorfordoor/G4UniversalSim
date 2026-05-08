#include "Physics/PhysicsFactory.hh"

#include "Utils/StringUtils.hh"

#include "G4DecayPhysics.hh"
#include "G4EmDNAPhysics.hh"
#include "G4EmLivermorePhysics.hh"
#include "G4EmPenelopePhysics.hh"
#include "G4EmStandardPhysics.hh"
#include "G4EmStandardPhysics_option1.hh"
#include "G4EmStandardPhysics_option2.hh"
#include "G4EmStandardPhysics_option3.hh"
#include "G4EmStandardPhysics_option4.hh"
#include "G4GenericBiasingPhysics.hh"
#include "G4HadronElasticPhysics.hh"
#include "G4HadronElasticPhysicsHP.hh"
#include "G4HadronPhysicsFTFP_BERT.hh"
#include "G4HadronPhysicsFTFP_BERT_HP.hh"
#include "G4HadronPhysicsFTFQGSP_BERT.hh"
#include "G4HadronPhysicsFTF_BIC.hh"
#include "G4HadronPhysicsQGSP_BERT.hh"
#include "G4HadronPhysicsQGSP_BERT_HP.hh"
#include "G4HadronPhysicsQGSP_BIC.hh"
#include "G4HadronPhysicsQGSP_FTFP_BERT.hh"
#include "G4IonINCLXXPhysics.hh"
#include "G4IonPhysics.hh"
#include "G4IonQMDPhysics.hh"
#include "G4OpticalPhysics.hh"
#include "G4PhysListFactory.hh"
#include "G4RadioactiveDecayPhysics.hh"
#include "G4StoppingPhysics.hh"
#include "G4VModularPhysicsList.hh"

#include <algorithm>
#include <iostream>
#include <map>
#include <stdexcept>

namespace {

const std::map<std::string, std::string>& AliasMap()
{
    static const std::map<std::string, std::string> aliases = {
        {"g4emstandardphysics", "G4EmStandardPhysics"},
        {"em_standard", "G4EmStandardPhysics"},
        {"standard", "G4EmStandardPhysics"},

        {"g4emstandardphysics_option1", "G4EmStandardPhysics_option1"},
        {"em_option1", "G4EmStandardPhysics_option1"},
        {"option1", "G4EmStandardPhysics_option1"},

        {"g4emstandardphysics_option2", "G4EmStandardPhysics_option2"},
        {"em_option2", "G4EmStandardPhysics_option2"},
        {"option2", "G4EmStandardPhysics_option2"},

        {"g4emstandardphysics_option3", "G4EmStandardPhysics_option3"},
        {"em_option3", "G4EmStandardPhysics_option3"},
        {"option3", "G4EmStandardPhysics_option3"},

        {"g4emstandardphysics_option4", "G4EmStandardPhysics_option4"},
        {"em_option4", "G4EmStandardPhysics_option4"},
        {"option4", "G4EmStandardPhysics_option4"},
        {"em4", "G4EmStandardPhysics_option4"},

        {"g4emlivermorephysics", "G4EmLivermorePhysics"},
        {"livermore", "G4EmLivermorePhysics"},
        {"em_livermore", "G4EmLivermorePhysics"},

        {"g4empenelopephysics", "G4EmPenelopePhysics"},
        {"penelope", "G4EmPenelopePhysics"},
        {"em_penelope", "G4EmPenelopePhysics"},

        {"g4emdna", "G4EmDNAPhysics"},
        {"g4emdnaphysics", "G4EmDNAPhysics"},
        {"dna", "G4EmDNAPhysics"},
        {"em_dna", "G4EmDNAPhysics"},

        {"g4hadronphysicsftfp_bert", "G4HadronPhysicsFTFP_BERT"},
        {"ftfp_bert", "G4HadronPhysicsFTFP_BERT"},
        {"bert", "G4HadronPhysicsFTFP_BERT"},

        {"g4hadronphysicsftfp_bert_hp", "G4HadronPhysicsFTFP_BERT_HP"},
        {"ftfp_bert_hp", "G4HadronPhysicsFTFP_BERT_HP"},
        {"bert_hp", "G4HadronPhysicsFTFP_BERT_HP"},

        {"g4hadronphysicsqgsp_bert", "G4HadronPhysicsQGSP_BERT"},
        {"qgsp_bert", "G4HadronPhysicsQGSP_BERT"},

        {"g4hadronphysicsqgsp_bert_hp", "G4HadronPhysicsQGSP_BERT_HP"},
        {"qgsp_bert_hp", "G4HadronPhysicsQGSP_BERT_HP"},

        {"g4hadronphysicsqgsp_bic", "G4HadronPhysicsQGSP_BIC"},
        {"qgsp_bic", "G4HadronPhysicsQGSP_BIC"},

        {"g4hadronphysicsftf_bic", "G4HadronPhysicsFTF_BIC"},
        {"ftf_bic", "G4HadronPhysicsFTF_BIC"},

        {"g4hadronphysicsqgsp_ftfp_bert", "G4HadronPhysicsQGSP_FTFP_BERT"},
        {"qgsp_ftfp_bert", "G4HadronPhysicsQGSP_FTFP_BERT"},

        {"g4hadronphysicsftfqgsp_bert", "G4HadronPhysicsFTFQGSP_BERT"},
        {"ftfqgsp_bert", "G4HadronPhysicsFTFQGSP_BERT"},

        {"g4hadronelasticphysics", "G4HadronElasticPhysics"},
        {"elastic", "G4HadronElasticPhysics"},
        {"hel", "G4HadronElasticPhysics"},

        {"g4hadronelasticphysicshp", "G4HadronElasticPhysicsHP"},
        {"elastichp", "G4HadronElasticPhysicsHP"},
        {"helhp", "G4HadronElasticPhysicsHP"},

        {"g4ionphysics", "G4IonPhysics"},
        {"ion", "G4IonPhysics"},
        {"ionphysics", "G4IonPhysics"},

        {"g4ioninclxxphysics", "G4IonINCLXXPhysics"},
        {"ioninclxx", "G4IonINCLXXPhysics"},
        {"ionincl", "G4IonINCLXXPhysics"},

        {"g4ionqmdphysics", "G4IonQMDPhysics"},
        {"ionqmd", "G4IonQMDPhysics"},
        {"ionqmdphysics", "G4IonQMDPhysics"},

        {"g4decayphysics", "G4DecayPhysics"},
        {"decay", "G4DecayPhysics"},

        {"g4radioactivedecayphysics", "G4RadioactiveDecayPhysics"},
        {"radioactive_decay", "G4RadioactiveDecayPhysics"},
        {"rdm", "G4RadioactiveDecayPhysics"},

        {"g4stoppingphysics", "G4StoppingPhysics"},
        {"stopping", "G4StoppingPhysics"},

        {"g4opticalphysics", "G4OpticalPhysics"},
        {"optical", "G4OpticalPhysics"},

        {"g4genericbiasingphysics", "G4GenericBiasingPhysics"},
        {"generic_biasing", "G4GenericBiasingPhysics"}
    };
    return aliases;
}

template <typename T>
std::unique_ptr<G4VPhysicsConstructor> Make()
{
    return std::make_unique<T>();
}

} // namespace

std::string PhysicsFactory::NormalizeOptionName(const std::string& option)
{
    const auto key = StringUtils::ToLower(StringUtils::Trim(option));
    if (key.empty()) {
        throw std::runtime_error("PhysicsFactory::NormalizeOptionName failed: empty option");
    }

    const auto iter = AliasMap().find(key);
    if (iter == AliasMap().end()) {
        throw std::runtime_error("Unknown physics option: '" + option + "'");
    }
    return iter->second;
}

PhysicsCategory PhysicsFactory::Classify(const std::string& canonicalName)
{
    const auto name = NormalizeOptionName(canonicalName);
    if (StringUtils::StartsWith(name, "G4Em")) return PhysicsCategory::EM;
    if (StringUtils::StartsWith(name, "G4HadronPhysics")) return PhysicsCategory::Hadronic;
    if (StringUtils::StartsWith(name, "G4HadronElastic")) return PhysicsCategory::Elastic;
    if (StringUtils::StartsWith(name, "G4Ion")) return PhysicsCategory::Ion;
    if (name == "G4DecayPhysics" || name == "G4RadioactiveDecayPhysics") return PhysicsCategory::Decay;
    if (name == "G4StoppingPhysics") return PhysicsCategory::Stopping;
    if (name == "G4OpticalPhysics") return PhysicsCategory::Optical;
    if (name == "G4GenericBiasingPhysics") return PhysicsCategory::Biasing;
    return PhysicsCategory::Other;
}

bool PhysicsFactory::IsKnownOption(const std::string& option)
{
    try {
        (void)NormalizeOptionName(option);
        return true;
    } catch (...) {
        return false;
    }
}

std::unique_ptr<G4VPhysicsConstructor>
PhysicsFactory::CreatePhysicsConstructor(const std::string& option)
{
    const auto name = NormalizeOptionName(option);

    if (name == "G4EmStandardPhysics") return Make<G4EmStandardPhysics>();
    if (name == "G4EmStandardPhysics_option1") return Make<G4EmStandardPhysics_option1>();
    if (name == "G4EmStandardPhysics_option2") return Make<G4EmStandardPhysics_option2>();
    if (name == "G4EmStandardPhysics_option3") return Make<G4EmStandardPhysics_option3>();
    if (name == "G4EmStandardPhysics_option4") return Make<G4EmStandardPhysics_option4>();
    if (name == "G4EmLivermorePhysics") return Make<G4EmLivermorePhysics>();
    if (name == "G4EmPenelopePhysics") return Make<G4EmPenelopePhysics>();
    if (name == "G4EmDNAPhysics") return Make<G4EmDNAPhysics>();

    if (name == "G4HadronPhysicsFTFP_BERT") return Make<G4HadronPhysicsFTFP_BERT>();
    if (name == "G4HadronPhysicsFTFP_BERT_HP") return Make<G4HadronPhysicsFTFP_BERT_HP>();
    if (name == "G4HadronPhysicsQGSP_BERT") return Make<G4HadronPhysicsQGSP_BERT>();
    if (name == "G4HadronPhysicsQGSP_BERT_HP") return Make<G4HadronPhysicsQGSP_BERT_HP>();
    if (name == "G4HadronPhysicsQGSP_BIC") return Make<G4HadronPhysicsQGSP_BIC>();
    if (name == "G4HadronPhysicsFTF_BIC") return Make<G4HadronPhysicsFTF_BIC>();
    if (name == "G4HadronPhysicsQGSP_FTFP_BERT") return Make<G4HadronPhysicsQGSP_FTFP_BERT>();
    if (name == "G4HadronPhysicsFTFQGSP_BERT") return Make<G4HadronPhysicsFTFQGSP_BERT>();

    if (name == "G4HadronElasticPhysics") return Make<G4HadronElasticPhysics>();
    if (name == "G4HadronElasticPhysicsHP") return Make<G4HadronElasticPhysicsHP>();

    if (name == "G4IonPhysics") return Make<G4IonPhysics>();
    if (name == "G4IonINCLXXPhysics") return Make<G4IonINCLXXPhysics>();
    if (name == "G4IonQMDPhysics") return Make<G4IonQMDPhysics>();

    if (name == "G4DecayPhysics") return Make<G4DecayPhysics>();
    if (name == "G4RadioactiveDecayPhysics") return Make<G4RadioactiveDecayPhysics>();
    if (name == "G4StoppingPhysics") return Make<G4StoppingPhysics>();
    if (name == "G4OpticalPhysics") return Make<G4OpticalPhysics>();
    if (name == "G4GenericBiasingPhysics") return Make<G4GenericBiasingPhysics>();

    throw std::runtime_error("PhysicsFactory failed to create constructor for option: '" + option + "'");
}

std::unique_ptr<G4VPhysicsConstructor>
PhysicsFactory::CreateGenericBiasingPhysics(const std::vector<std::string>& particleNames)
{
    std::map<std::string, std::vector<std::string>> particleProcesses;
    for (const auto& particleName : particleNames) {
        const auto trimmed = StringUtils::Trim(particleName);
        if (!trimmed.empty()) particleProcesses[trimmed] = {};
    }
    return CreateGenericBiasingPhysics(particleProcesses);
}

std::unique_ptr<G4VPhysicsConstructor>
PhysicsFactory::CreateGenericBiasingPhysics(
    const std::map<std::string, std::vector<std::string>>& particleProcesses)
{
    auto biasing = std::make_unique<G4GenericBiasingPhysics>();
    std::size_t configuredParticles = 0;

    for (const auto& item : particleProcesses) {
        const auto particleName = StringUtils::Trim(item.first);
        if (particleName.empty()) continue;

        if (item.second.empty()) {
            biasing->PhysicsBias(particleName);
        } else {
            std::vector<G4String> processes;
            for (const auto& process : item.second) {
                const auto trimmed = StringUtils::Trim(process);
                if (!trimmed.empty()) processes.emplace_back(trimmed);
            }
            if (processes.empty()) {
                biasing->PhysicsBias(particleName);
            } else {
                biasing->PhysicsBias(particleName, processes);
            }
        }
        ++configuredParticles;
    }

    if (configuredParticles == 0) {
        throw std::runtime_error(
            "PhysicsFactory::CreateGenericBiasingPhysics failed: no biased particle names were provided");
    }

    return biasing;
}

std::vector<std::string> PhysicsFactory::AvailableAliases()
{
    std::vector<std::string> aliases;
    aliases.reserve(AliasMap().size());
    for (const auto& item : AliasMap()) {
        aliases.push_back(item.first);
    }
    return aliases;
}

bool PhysicsFactory::IsKnownReferenceList(const std::string& referenceName)
{
    const auto name = StringUtils::Trim(referenceName);
    if (name.empty()) return false;
    G4PhysListFactory factory;
    return factory.IsReferencePhysList(name);
}

std::vector<std::string> PhysicsFactory::AvailableReferenceLists()
{
    G4PhysListFactory factory;
    std::vector<std::string> values;
    for (const auto& name : factory.AvailablePhysLists()) {
        values.emplace_back(name);
    }
    if (!values.empty()) return values;

    return {
        "FTFP_BERT", "FTFP_BERT_HP", "FTFP_BERT_EMZ",
        "FTFP_BERT_LIV", "FTFP_BERT_PEN", "QGSP_BERT",
        "QGSP_BIC", "Shielding"
    };
}

std::vector<std::string> PhysicsFactory::AvailableReferenceListsEM()
{
    G4PhysListFactory factory;
    std::vector<std::string> values;
    for (const auto& name : factory.AvailablePhysListsEM()) {
        values.emplace_back(name);
    }
    if (!values.empty()) return values;

    return {"_EMV", "_EMX", "_EMY", "_EMZ", "_LIV", "_PEN", "_DNA"};
}

std::unique_ptr<G4VModularPhysicsList>
PhysicsFactory::CreateReferencePhysicsList(const std::string& referenceName)
{
    const auto name = StringUtils::Trim(referenceName);
    if (name.empty()) {
        throw std::runtime_error("PhysicsFactory::CreateReferencePhysicsList failed: referenceName is empty");
    }

    G4PhysListFactory factory;
    if (!factory.IsReferencePhysList(name)) {
        throw std::runtime_error("Unknown Geant4 reference physics list: '" + referenceName + "'");
    }

    auto* list = factory.GetReferencePhysList(name);
    if (!list) {
        throw std::runtime_error("G4PhysListFactory returned null for reference physics list: '" + referenceName + "'");
    }
    return std::unique_ptr<G4VModularPhysicsList>(list);
}

void PhysicsFactory::RegisterExtraModule(G4VModularPhysicsList* list,
                                         const std::string& option)
{
    if (!list) {
        throw std::runtime_error("PhysicsFactory::RegisterExtraModule failed: physics list is null");
    }

    const auto canonical = NormalizeOptionName(option);
    if (Classify(canonical) == PhysicsCategory::EM) {
        throw std::runtime_error(
            "PhysicsFactory::RegisterExtraModule failed: EM physics should be selected by reference suffix in reference mode, option='" +
            option + "'");
    }
    if (Classify(canonical) == PhysicsCategory::Biasing) {
        throw std::runtime_error(
            "PhysicsFactory::RegisterExtraModule failed: generic biasing needs configured particle names; use RegisterGenericBiasingPhysics");
    }

    auto physics = CreatePhysicsConstructor(canonical);
    list->RegisterPhysics(physics.release());
}

void PhysicsFactory::RegisterExtraModules(G4VModularPhysicsList* list,
                                          const std::vector<std::string>& options)
{
    for (const auto& option : options) {
        RegisterExtraModule(list, option);
    }
}

void PhysicsFactory::RegisterGenericBiasingPhysics(
    G4VModularPhysicsList* list,
    const std::map<std::string, std::vector<std::string>>& particleProcesses)
{
    if (!list) {
        throw std::runtime_error("PhysicsFactory::RegisterGenericBiasingPhysics failed: physics list is null");
    }
    auto physics = CreateGenericBiasingPhysics(particleProcesses);
    list->RegisterPhysics(physics.release());
}

std::string PhysicsFactory::StripEMSuffix(const std::string& referenceName)
{
    auto name = StringUtils::Trim(referenceName);
    const std::vector<std::string> suffixes = {
        "_EMV", "_EMX", "_EMY", "_EMZ", "_LIV", "_PEN", "_DNA"
    };
    const auto lowerName = StringUtils::ToLower(name);
    for (const auto& suffix : suffixes) {
        const auto lowerSuffix = StringUtils::ToLower(suffix);
        if (lowerName.size() >= lowerSuffix.size() &&
            lowerName.compare(lowerName.size() - lowerSuffix.size(), lowerSuffix.size(), lowerSuffix) == 0) {
            name.erase(name.size() - suffix.size());
            break;
        }
    }
    return name;
}

std::string PhysicsFactory::NormalizeEMOptionForReference(const std::string& emOption)
{
    const auto key = StringUtils::ToLower(StringUtils::Trim(emOption));
    if (key.empty() || key == "default" || key == "standard" || key == "em_standard") return "";
    if (key == "option1" || key == "em_option1" || key == "emv") return "_EMV";
    if (key == "option2" || key == "em_option2" || key == "emx") return "_EMX";
    if (key == "option3" || key == "em_option3" || key == "emy") return "_EMY";
    if (key == "option4" || key == "em_option4" || key == "em4" || key == "emz") return "_EMZ";
    if (key == "livermore" || key == "em_livermore" || key == "liv") return "_LIV";
    if (key == "penelope" || key == "em_penelope" || key == "pen") return "_PEN";
    if (key == "dna" || key == "em_dna") return "_DNA";
    throw std::runtime_error("Cannot map EM option to reference-list suffix: '" + emOption + "'");
}

std::string PhysicsFactory::ApplyEMSuffixToReference(const std::string& baseReference,
                                                     const std::string& emOption)
{
    const auto base = StripEMSuffix(baseReference);
    if (base.empty()) {
        throw std::runtime_error("PhysicsFactory::ApplyEMSuffixToReference failed: baseReference is empty");
    }
    return base + NormalizeEMOptionForReference(emOption);
}

void PhysicsFactory::ApplyCuts(G4VModularPhysicsList* list,
                               double defaultCut,
                               const std::map<std::string, double>& particleCuts)
{
    if (!list) {
        throw std::runtime_error("PhysicsFactory::ApplyCuts failed: physics list is null");
    }
    if (defaultCut <= 0.0) {
        throw std::runtime_error("PhysicsFactory::ApplyCuts failed: defaultCut must be > 0");
    }

    list->SetDefaultCutValue(defaultCut);
    for (const auto& item : particleCuts) {
        if (item.second <= 0.0) {
            throw std::runtime_error("PhysicsFactory::ApplyCuts failed: cut for particle '" +
                                     item.first + "' must be > 0");
        }
        list->SetCutValue(item.second, item.first);
    }
}
